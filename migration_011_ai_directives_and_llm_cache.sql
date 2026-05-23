-- Migration 011: AI Directives + LLM Semantic Cache
-- Run once: psql "$DATABASE_URL" -f migration_011_ai_directives_and_llm_cache.sql
-- Safe to re-run (uses IF NOT EXISTS).

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────
-- 1) ai_directives — سجلّ كامل لكل توجيه أنتجه الـ LLM
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_directives (
    id                  BIGSERIAL PRIMARY KEY,
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    horizon_hours       INTEGER     NOT NULL,           -- توقّع لكم ساعة (مثلاً 24, 168)
    input_window_hours  INTEGER     NOT NULL DEFAULT 48,
    input_snapshot      JSONB       NOT NULL,           -- البيانات الإجمالية التي رآها الـ LLM
    prompt_hash         BYTEA       NOT NULL,           -- SHA-256(canonical prompt)
    model               VARCHAR(40) NOT NULL,
    directive_ar        TEXT        NOT NULL,           -- التوجيه التشغيلي بالعربي
    summary_ar          TEXT,                            -- ملخّص قصير (اختياري للـ subject line)
    confidence          NUMERIC(3,2),                    -- 0.00–1.00 من تقدير LLM لنفسه
    affected_master_ids INTEGER[],                       -- متاجر استهدفها التوجيه
    token_input         INTEGER,
    token_output        INTEGER,
    cost_usd            NUMERIC(8,5),
    cache_hit           BOOLEAN     DEFAULT FALSE,
    superseded_by       BIGINT      REFERENCES ai_directives(id),  -- لما يصير توجيه أحدث على نفس النطاق
    feedback            VARCHAR(20)                      -- 'acted' | 'ignored' | 'wrong' (للتعلم لاحقاً)
);

COMMENT ON TABLE ai_directives IS
    'سجلّ كل توجيه أنتجه الـ LLM. cache_hit=TRUE يعني الرد جاء من llm_semantic_cache بلا استدعاء.';

CREATE INDEX IF NOT EXISTS idx_directives_prompt_hash
    ON ai_directives (prompt_hash);

CREATE INDEX IF NOT EXISTS idx_directives_recent_active
    ON ai_directives (generated_at DESC)
    WHERE superseded_by IS NULL;

CREATE INDEX IF NOT EXISTS idx_directives_model
    ON ai_directives (model, generated_at DESC);

-- ──────────────────────────────────────────────────────────────────────────
-- 2) llm_semantic_cache — تخزين كاش الـ LLM responses
--    Week 3: exact-hash cache (BYTEA SHA-256). الـ semantic similarity
--    (pgvector + embeddings) يُضاف في Week 3.5 عند الحاجة.
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_semantic_cache (
    id              BIGSERIAL    PRIMARY KEY,
    purpose         VARCHAR(40)  NOT NULL,              -- 'directive' | 'seo_copy' | 'social_reply'
    prompt_text     TEXT         NOT NULL,
    prompt_hash     BYTEA        NOT NULL UNIQUE,       -- SHA-256(canonical prompt) — exact match
    response_text   TEXT         NOT NULL,
    response_json   JSONB,                              -- لو الرد structured
    model           VARCHAR(40)  NOT NULL,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    tokens_saved    INTEGER      DEFAULT 0,             -- يتراكم مع كل cache hit
    hit_count       INTEGER      DEFAULT 0,
    last_hit_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ  NOT NULL               -- TTL حسب الـ purpose
);

COMMENT ON TABLE llm_semantic_cache IS
    'كاش استدعاءات الـ LLM. عند exact-hash hit، يُسترجع الرد بدون استدعاء جديد ⇒ توفير 100% تكلفة.';

CREATE INDEX IF NOT EXISTS idx_llm_cache_purpose_expires
    ON llm_semantic_cache (purpose, expires_at);

-- ──────────────────────────────────────────────────────────────────────────
-- 3) llm_call_log — سجل اختصاري لكل استدعاء LLM (للـ debugging والـ audit)
-- ──────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS llm_call_log (
    id              BIGSERIAL    PRIMARY KEY,
    called_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    purpose         VARCHAR(40)  NOT NULL,
    model           VARCHAR(40)  NOT NULL,
    cache_hit       BOOLEAN      DEFAULT FALSE,
    tokens_input    INTEGER,
    tokens_output   INTEGER,
    cost_usd        NUMERIC(8,5),
    latency_ms      INTEGER,
    success         BOOLEAN      NOT NULL,
    error_message   TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_log_day
    ON llm_call_log (called_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_log_failures
    ON llm_call_log (called_at DESC)
    WHERE success = FALSE;

COMMIT;
