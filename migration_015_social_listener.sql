-- Migration 015: Social Listener + Auto-Responder (Week 7-8)
-- Run once: psql "$DATABASE_URL" -f migration_015_social_listener.sql
-- آمن لإعادة التشغيل (IF NOT EXISTS + بذور ON CONFLICT DO NOTHING).

BEGIN;

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1) مصطلحات الرصد — الكلمات/الهاشتاقات التي نراقبها
CREATE TABLE IF NOT EXISTS social_listening_terms (
    id                   SERIAL PRIMARY KEY,
    platform             VARCHAR(20),              -- 'x' | 'telegram' | 'instagram' | 'any'
    term                 TEXT NOT NULL,
    term_type            VARCHAR(20),              -- 'keyword' | 'regex' | 'hashtag'
    associated_master_id INTEGER REFERENCES master(id) ON DELETE SET NULL,
    intent_weight        NUMERIC(3,2) DEFAULT 1.00,
    active               BOOLEAN DEFAULT TRUE,
    UNIQUE (platform, term)
);

-- 2) قوالب الردود — A/B + نبرة
CREATE TABLE IF NOT EXISTS social_response_templates (
    id          SERIAL PRIMARY KEY,
    template_ar TEXT NOT NULL,
    template_en TEXT,
    tone        VARCHAR(20),
    active       BOOLEAN DEFAULT TRUE,
    a_b_group   CHAR(1)
);

-- 3) الإشارات المرصودة (mentions)
CREATE TABLE IF NOT EXISTS social_signals (
    id                  BIGSERIAL PRIMARY KEY,
    platform            VARCHAR(20),
    external_id         VARCHAR(120) NOT NULL,
    author_handle       VARCHAR(80),
    author_followers    INTEGER,
    content             TEXT NOT NULL,
    lang_detected       CHAR(2),
    intent_score        NUMERIC(3,2),
    matched_term_id     INTEGER REFERENCES social_listening_terms(id) ON DELETE SET NULL,
    candidate_master_ids INTEGER[],
    source_url          TEXT,
    captured_at         TIMESTAMPTZ DEFAULT NOW(),
    posted_at           TIMESTAMPTZ,
    status              VARCHAR(20) DEFAULT 'new',  -- new|scored|matched|responded|ignored
    UNIQUE (platform, external_id)
);

CREATE INDEX IF NOT EXISTS idx_social_signals_status
    ON social_signals (status) WHERE status IN ('new', 'scored', 'matched');
CREATE INDEX IF NOT EXISTS idx_social_signals_recent
    ON social_signals (captured_at DESC);

-- 4) الردود المُجهّزة/المنشورة
CREATE TABLE IF NOT EXISTS social_responses (
    id                  BIGSERIAL PRIMARY KEY,
    signal_id           BIGINT REFERENCES social_signals(id) ON DELETE CASCADE,
    master_id           INTEGER REFERENCES master(id) ON DELETE SET NULL,
    template_id         INTEGER REFERENCES social_response_templates(id) ON DELETE SET NULL,
    rendered_text       TEXT NOT NULL,
    link_url            TEXT,
    review_status       VARCHAR(20) DEFAULT 'pending',  -- pending|auto_approved|approved|posted|rejected|failed
    posted_external_id  VARCHAR(120),
    posted_at           TIMESTAMPTZ,
    engagement_json     JSONB,
    affiliate_clicks    INTEGER DEFAULT 0,
    revenue_attributed_usd NUMERIC(8,2) DEFAULT 0,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_social_responses_review
    ON social_responses (review_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_social_responses_signal
    ON social_responses (signal_id);

-- ── بذور افتراضية (تشتغل مباشرة بدون إعداد) ────────────────────────────────
INSERT INTO social_listening_terms (platform, term, term_type, intent_weight, active) VALUES
    ('any', 'كود خصم',  'keyword', 1.00, TRUE),
    ('any', 'كوبون',    'keyword', 1.00, TRUE),
    ('any', 'خصم',      'keyword', 0.70, TRUE),
    ('any', 'تخفيضات',  'keyword', 0.80, TRUE),
    ('any', 'عرض',      'keyword', 0.50, TRUE),
    ('any', 'بكم سعر',  'keyword', 0.60, TRUE)
ON CONFLICT (platform, term) DO NOTHING;

INSERT INTO social_response_templates (template_ar, tone, active, a_b_group) VALUES
    ('لقيت لك كوبون خصم {store} 🎁 وفّر الحين من هنا: {link}', 'friendly', TRUE, 'A'),
    ('عروض {store} وكودها محدّث ✅ كل التفاصيل: {link}',        'friendly', TRUE, 'B')
ON CONFLICT DO NOTHING;

COMMIT;
