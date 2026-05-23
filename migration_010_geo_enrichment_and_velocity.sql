-- Migration 010: Geo enrichment + Velocity snapshots + AI alert ledger
-- Run once: psql "$DATABASE_URL" -f migration_010_geo_enrichment_and_velocity.sql
-- Safe to re-run (every DDL uses IF NOT EXISTS / IF EXISTS).

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────
-- 1) إثراء action_logs بأعمدة الـ Geo والـ Fraud Quality
-- ──────────────────────────────────────────────────────────────────────────
ALTER TABLE action_logs
    ADD COLUMN IF NOT EXISTS event_id        UUID        DEFAULT gen_random_uuid(),
    ADD COLUMN IF NOT EXISTS ip_hash         BYTEA,
    ADD COLUMN IF NOT EXISTS country_code    CHAR(2),
    ADD COLUMN IF NOT EXISTS region_code     VARCHAR(8),
    ADD COLUMN IF NOT EXISTS city            VARCHAR(80),
    ADD COLUMN IF NOT EXISTS postal_code     VARCHAR(16),
    ADD COLUMN IF NOT EXISTS lat             NUMERIC(8,5),
    ADD COLUMN IF NOT EXISTS lng             NUMERIC(8,5),
    ADD COLUMN IF NOT EXISTS accuracy_km     SMALLINT,
    ADD COLUMN IF NOT EXISTS isp             VARCHAR(120),
    ADD COLUMN IF NOT EXISTS asn             INTEGER,
    ADD COLUMN IF NOT EXISTS is_datacenter   BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS is_proxy        BOOLEAN     DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS device_class    VARCHAR(20),
    ADD COLUMN IF NOT EXISTS user_agent_hash BYTEA,
    ADD COLUMN IF NOT EXISTS cf_bot_score    SMALLINT,
    ADD COLUMN IF NOT EXISTS quality_score   SMALLINT    DEFAULT 100;

COMMENT ON COLUMN action_logs.event_id IS
    'مفتاح فريد لكل حدث — يُمكِّن client-side retry idempotency.';
COMMENT ON COLUMN action_logs.ip_hash IS
    'SHA-256(ip + daily_salt) — لا نُخزّن الـ IP الخام أبداً.';
COMMENT ON COLUMN action_logs.quality_score IS
    '0..100 — درجة جودة الحدث (مرتفع = ثقة عالية، منخفض = bot/datacenter).';

-- البحث الـ idempotent عن الحدث (إعادة محاولات العميل، replays من Redis)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_actionlogs_event_id
    ON action_logs (event_id);

-- المسار الساخن: نشاط متجر معيّن في فترة حديثة (مصدر الـ matview + كاشف الذروة)
CREATE INDEX IF NOT EXISTS idx_actionlogs_store_time
    ON action_logs (store_id, action_time DESC)
    WHERE action_type IN ('click_link', 'copy_coupon');

-- تحليلات الـ Geo (full index — PostgreSQL لا يقبل NOW() في الـ predicate
-- لأنها STABLE وليست IMMUTABLE. نُغطّي كل البيانات، الحجم لا يزال صغيراً
-- لأن country_code + city صغيران)
CREATE INDEX IF NOT EXISTS idx_actionlogs_geo_recent
    ON action_logs (country_code, city, action_time DESC);

-- استعلامات الـ Fraud (لاستبعاد الأحداث المعزولة من التجميعات)
CREATE INDEX IF NOT EXISTS idx_actionlogs_quality
    ON action_logs (quality_score, action_time DESC)
    WHERE quality_score < 70;

-- ──────────────────────────────────────────────────────────────────────────
-- 2) جدول لقطات السرعة (Velocity Snapshots) — البنية الأساسية لكشف الذروة
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS coupon_velocity_snapshots (
    id                 BIGSERIAL PRIMARY KEY,
    master_id          INTEGER     NOT NULL REFERENCES master(id) ON DELETE CASCADE,
    bucket_start       TIMESTAMPTZ NOT NULL,
    bucket_minutes     SMALLINT    NOT NULL DEFAULT 5,
    clicks             INTEGER     NOT NULL DEFAULT 0,
    copies             INTEGER     NOT NULL DEFAULT 0,
    searches           INTEGER     NOT NULL DEFAULT 0,
    unique_visitors    INTEGER     NOT NULL DEFAULT 0,
    top_country        CHAR(2),
    top_city           VARCHAR(80),
    geo_concentration  NUMERIC(4,3),
    avg_quality_score  SMALLINT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uniq_master_bucket
        UNIQUE (master_id, bucket_start, bucket_minutes)
);

COMMENT ON TABLE coupon_velocity_snapshots IS
    'لقطات تجميعية بـ Buckets زمنية (5 دقائق افتراضياً) لكل متجر — تُغذّي كاشف الذروة وتقارير الأداء.';

-- index كامل على bucket_start — predicate مع NOW() غير مسموح في PG
CREATE INDEX IF NOT EXISTS idx_velocity_bucket_recent
    ON coupon_velocity_snapshots (bucket_start DESC, master_id);

-- ──────────────────────────────────────────────────────────────────────────
-- 3) Materialized view: خط الأساس لنافذة 48 ساعة (z-score baseline)
-- ──────────────────────────────────────────────────────────────────────────
DROP MATERIALIZED VIEW IF EXISTS mv_store_velocity_48h;
CREATE MATERIALIZED VIEW mv_store_velocity_48h AS
SELECT
    master_id,
    COALESCE(SUM(clicks + copies) FILTER (WHERE bucket_start > NOW() - INTERVAL '1 hour'),  0) AS recent_1h,
    COALESCE(SUM(clicks + copies) FILTER (WHERE bucket_start > NOW() - INTERVAL '6 hour'),  0) AS recent_6h,
    COALESCE(SUM(clicks + copies) FILTER (WHERE bucket_start > NOW() - INTERVAL '48 hour'), 0) AS recent_48h,
    COALESCE(AVG(clicks + copies)::numeric(8,3), 0)         AS hourly_mean,
    COALESCE(STDDEV_POP(clicks + copies)::numeric(8,3), 0)  AS hourly_stddev,
    MAX(bucket_start)                                       AS latest_bucket
FROM coupon_velocity_snapshots
WHERE bucket_minutes = 5
  AND bucket_start > NOW() - INTERVAL '14 days'
GROUP BY master_id;

-- UNIQUE INDEX إجباري لاستخدام REFRESH CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS uniq_mv_store_velocity_48h
    ON mv_store_velocity_48h (master_id);

-- ──────────────────────────────────────────────────────────────────────────
-- 4) سجلّ تنبيهات الـ AI (idempotent) — يُستخدم في Feature 1 و Financial Guardian
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_alerts (
    id                 BIGSERIAL PRIMARY KEY,
    alert_type         VARCHAR(40)  NOT NULL,
    master_id          INTEGER REFERENCES master(id) ON DELETE SET NULL,
    severity           VARCHAR(10)  NOT NULL,        -- 'info' | 'warning' | 'critical'
    idempotency_key    VARCHAR(160) NOT NULL UNIQUE,
    title              TEXT,
    body               TEXT         NOT NULL,
    context_json       JSONB        NOT NULL,
    dispatched_at      TIMESTAMPTZ,
    dispatch_channel   VARCHAR(20),                  -- 'email' | 'dashboard'
    dispatch_status    VARCHAR(20)  DEFAULT 'pending',
    dispatch_error     TEXT,
    acknowledged_at    TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE ai_alerts IS
    'سجلّ مركزي لكل تنبيه آلي — الـ idempotency_key يمنع تكرار الإيميلات.';

CREATE INDEX IF NOT EXISTS idx_alerts_pending
    ON ai_alerts (created_at)
    WHERE dispatch_status = 'pending';

CREATE INDEX IF NOT EXISTS idx_alerts_by_store_type
    ON ai_alerts (master_id, alert_type, created_at DESC);

COMMIT;

-- ──────────────────────────────────────────────────────────────────────────
-- بعد أول بيانات تصل لـ coupon_velocity_snapshots، شغّل التحديث الأول يدوياً:
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_store_velocity_48h;
-- ثم اضبط cron job كل دقيقة على نفس الأمر.
-- ──────────────────────────────────────────────────────────────────────────
