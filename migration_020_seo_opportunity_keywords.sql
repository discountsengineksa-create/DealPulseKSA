-- migration_020_seo_opportunity_keywords.sql
-- Phase: SEO Opportunity Engine (محرك الفرص)
-- يخزن الكلمات التي يضيفها المستخدم يدوياً + درجة Google Trends لكل منها
-- يُحدّث آلياً كل ساعة عبر api/seo/trends_puller.refresh_all_active_keywords()

CREATE TABLE IF NOT EXISTS seo_opportunity_keywords (
    id                  BIGSERIAL PRIMARY KEY,
    keyword             TEXT NOT NULL,
    store_id            TEXT,                            -- اختياري: ربط بمتجر في master
    notes               TEXT,                            -- ملاحظات المستخدم
    active              BOOLEAN DEFAULT TRUE,            -- لإيقاف keyword بدون حذفه
    -- بيانات Google Trends (تتحدث كل ساعة)
    trend_score         INTEGER DEFAULT 0,               -- 0-100, آخر نقطة timeseries
    trend_avg           NUMERIC(6, 2) DEFAULT 0,         -- متوسط الفترة كاملة
    rising_pct          NUMERIC(8, 2) DEFAULT 0,         -- % تغير آخر نقطة عن المتوسط
    last_checked_at     TIMESTAMPTZ,
    last_error          TEXT,                            -- آخر خطأ من pytrends لو فشل
    -- ربط بصفحة منشورة (لو ولّدنا واحدة لهذه الكلمة)
    generated_page_id   BIGINT,                          -- FK لـ seo_landing_pages.id (loose)
    -- audit
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    -- منع تكرار نفس الكلمة (case-insensitive)
    UNIQUE (keyword)
);

CREATE INDEX IF NOT EXISTS idx_seo_opp_active_score
    ON seo_opportunity_keywords (active, trend_score DESC);
CREATE INDEX IF NOT EXISTS idx_seo_opp_store
    ON seo_opportunity_keywords (store_id) WHERE store_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_seo_opp_last_checked
    ON seo_opportunity_keywords (last_checked_at NULLS FIRST);

-- ملاحظة: لا seed افتراضي — المستخدم يضيف keywords من الداشبورد.
