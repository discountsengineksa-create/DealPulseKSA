-- Migration 016: Cross-cutting tables (كانت مؤجَّلة في الخطة)
--   alert_quiet_hours  — كتم تنبيهات الإيميل في ساعات معيّنة
--   ai_experiments     — A/B testing لقرارات الـ AI (+ ai_experiment_events)
--   pdpl_audit_log     — سجل تدقيق لعمليات الأدمن (التزام PDPL السعودي)
-- Run once: psql "$DATABASE_URL" -f migration_016_crosscutting.sql
-- آمن لإعادة التشغيل (IF NOT EXISTS + بذور ON CONFLICT DO NOTHING).

BEGIN;

-- ── 1) ساعات الهدوء للتنبيهات ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_quiet_hours (
    id          SERIAL PRIMARY KEY,
    label       VARCHAR(60),
    start_hour  SMALLINT NOT NULL CHECK (start_hour BETWEEN 0 AND 23),
    end_hour    SMALLINT NOT NULL CHECK (end_hour BETWEEN 0 AND 23),
    timezone    VARCHAR(40) DEFAULT 'Asia/Riyadh',
    channels    TEXT[] DEFAULT ARRAY['email'],
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- نافذة ليلية افتراضية (غير مفعّلة) — يفعّلها الأدمن بضغطة من الداشبورد
INSERT INTO alert_quiet_hours (label, start_hour, end_hour, timezone, channels, active)
SELECT 'ليلاً (افتراضي)', 23, 7, 'Asia/Riyadh', ARRAY['email'], FALSE
WHERE NOT EXISTS (SELECT 1 FROM alert_quiet_hours);

-- ── 2) تجارب الـ AI (A/B) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_experiments (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(80) UNIQUE NOT NULL,
    description TEXT,
    surface     VARCHAR(40),          -- 'social_template' | 'directive' | 'seo_title'
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_experiment_events (
    id            BIGSERIAL PRIMARY KEY,
    experiment_id INTEGER REFERENCES ai_experiments(id) ON DELETE CASCADE,
    arm           VARCHAR(40) NOT NULL,
    event_type    VARCHAR(20) NOT NULL,   -- 'impression' | 'click' | 'conversion'
    ref_id        BIGINT,
    value         NUMERIC(8,2) DEFAULT 0,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_experiment_events
    ON ai_experiment_events (experiment_id, arm, event_type);

INSERT INTO ai_experiments (name, description, surface, active) VALUES
    ('social_template_ab', 'A/B لقوالب الردود الاجتماعية', 'social_template', TRUE)
ON CONFLICT (name) DO NOTHING;

-- ── 3) سجل التدقيق (PDPL) ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pdpl_audit_log (
    id          BIGSERIAL PRIMARY KEY,
    actor       VARCHAR(80) NOT NULL DEFAULT 'admin',
    action      VARCHAR(60) NOT NULL,    -- 'seo_publish' | 'social_approve' | 'broadcast' | ...
    target      VARCHAR(160),            -- المعرّف/الـ slug المتأثّر
    status      VARCHAR(20) DEFAULT 'ok',
    meta        JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pdpl_audit_recent ON pdpl_audit_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pdpl_audit_action ON pdpl_audit_log (action, created_at DESC);

COMMIT;
