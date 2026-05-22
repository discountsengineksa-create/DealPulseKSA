BEGIN;

-- 1. جدول إشارات وصيحات البحث (Trend Signals)
CREATE TABLE IF NOT EXISTS trend_signals (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(30) NOT NULL,        -- 'google_trends', 'serpapi', 'internal_search'
    query_text TEXT NOT NULL,
    geo VARCHAR(10) DEFAULT 'SA',
    interest_score INTEGER,
    velocity_score NUMERIC(6,2),
    related_queries TEXT[],
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. جدول قائمة الكلمات المحظورة (Keyword Blocklist)
CREATE TABLE IF NOT EXISTS seo_keyword_blocklist (
    id SERIAL PRIMARY KEY,
    pattern TEXT NOT NULL UNIQUE,
    pattern_type VARCHAR(10),
    reason VARCHAR(60),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. جدول مراقبة وتتبع وظائف التوليد عبر الـ LLM (Generation Jobs)
CREATE TABLE IF NOT EXISTS seo_generation_jobs (
    id BIGSERIAL PRIMARY KEY,
    trend_signal_id BIGINT REFERENCES trend_signals(id),
    target_keyword TEXT NOT NULL,
    matched_master_id INTEGER REFERENCES master(id),
    state VARCHAR(20) DEFAULT 'queued',
    prompt_hash BYTEA,
    llm_model VARCHAR(40),
    cost_usd NUMERIC(8,5),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- 4. جدول صفحات الهبوط الأوتوماتيكية بنصوص الـ Markdown (Landing Pages)
CREATE TABLE IF NOT EXISTS seo_landing_pages (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(200) UNIQUE NOT NULL,
    target_keyword TEXT NOT NULL,
    master_id INTEGER REFERENCES master(id),
    lang CHAR(2) NOT NULL,
    title_meta VARCHAR(180),
    description_meta VARCHAR(280),
    body_markdown TEXT NOT NULL,
    body_html_hash BYTEA NOT NULL,
    generated_by_job_id BIGINT REFERENCES seo_generation_jobs(id),
    status VARCHAR(20) DEFAULT 'draft',
    published_at TIMESTAMPTZ,
    last_indexed_at TIMESTAMPTZ,
    current_position SMALLINT,
    organic_clicks_7d INTEGER DEFAULT 0,
    organic_impressions_7d INTEGER DEFAULT 0,
    retired_reason VARCHAR(40)
);

-- 5. جدول تتبع الأرشفة الفورية عبر خدمات محركات البحث (Index Submissions)
CREATE TABLE IF NOT EXISTS seo_index_submissions (
    id BIGSERIAL PRIMARY KEY,
    landing_page_id BIGINT REFERENCES seo_landing_pages(id),
    provider VARCHAR(20),                -- 'google_indexing_api', 'indexnow_bing'
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    response_code SMALLINT,
    response_json JSONB,
    indexed_confirmed_at TIMESTAMPTZ
);

COMMIT;