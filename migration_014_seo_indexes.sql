-- Migration 014: SEO Generator — فهارس ودِدَب (Week 5-6)
-- مكمّل لـ migration_013_seo_generator.sql (الجداول الخمسة).
-- يضيف الفهارس اللازمة لمسارات الـ workers + قيود منع التكرار.
-- Run once: psql "$DATABASE_URL" -f migration_014_seo_indexes.sql
-- آمن لإعادة التشغيل (IF NOT EXISTS في كل مكان).

BEGIN;

-- pg_trgm مطلوب لمطابقة الكلمة بالمتجر (similarity) — موجود في الإنتاج أصلاً
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── trend_signals ──────────────────────────────────────────────────────────
-- صف واحد متطوّر لكل (مصدر, كلمة, نطاق) — يسمح بـ UPSERT للمصدر internal_search
CREATE UNIQUE INDEX IF NOT EXISTS uniq_trend_signal_src_query
    ON trend_signals (source, query_text, geo);

CREATE INDEX IF NOT EXISTS idx_trend_signals_recent
    ON trend_signals (captured_at DESC);

CREATE INDEX IF NOT EXISTS idx_trend_signals_interest
    ON trend_signals (interest_score DESC);

-- ── seo_generation_jobs ────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_seo_jobs_state
    ON seo_generation_jobs (state)
    WHERE state IN ('queued', 'running');

-- منع إنشاء وظيفتين فعّالتين لنفس (الكلمة, المتجر) في آنٍ واحد
CREATE UNIQUE INDEX IF NOT EXISTS uniq_seo_job_active
    ON seo_generation_jobs (target_keyword, matched_master_id)
    WHERE state IN ('queued', 'running');

-- ── seo_landing_pages ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_seo_pages_status
    ON seo_landing_pages (status);

CREATE INDEX IF NOT EXISTS idx_seo_pages_master
    ON seo_landing_pages (master_id);

-- ── seo_index_submissions ──────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_seo_index_sub_page
    ON seo_index_submissions (landing_page_id);

COMMIT;
