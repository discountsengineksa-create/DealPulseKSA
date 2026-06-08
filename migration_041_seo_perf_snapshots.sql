-- ════════════════════════════════════════════════════════════════════════════
-- Migration 041: لقطات أداء SEO اليومية (PageSpeed + Search Console)
-- ════════════════════════════════════════════════════════════════════════════
-- يخزّن لقطة يومية واحدة لمتابعة تطوّر الأداء عبر الزمن:
--   - درجات PageSpeed (جوال): الأداء/SEO/الإتاحة/الممارسات
--   - أرقام Search Console (آخر 28 يوم): نقرات/ظهور/CTR/متوسط الترتيب
-- صف واحد لكل يوم (ON CONFLICT يحدّث). يملؤه كرون يومي + زر لقطة فورية.
--
-- التطبيق:  python api/run_migration.py migration_041_seo_perf_snapshots.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS seo_perf_snapshots (
    id                 BIGSERIAL PRIMARY KEY,
    snapshot_date      DATE NOT NULL UNIQUE,
    ps_performance     SMALLINT,
    ps_seo             SMALLINT,
    ps_accessibility   SMALLINT,
    ps_best_practices  SMALLINT,
    gsc_clicks         INTEGER,
    gsc_impressions    INTEGER,
    gsc_ctr            NUMERIC(6,4),
    gsc_position       NUMERIC(6,2),
    created_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seo_perf_snapshots_date
    ON seo_perf_snapshots (snapshot_date DESC);

COMMIT;
