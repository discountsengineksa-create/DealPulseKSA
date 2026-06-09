-- migration_042_seo_keyword_volume.sql
-- Phase: محرك الفرص — إضافة حجم البحث الشهري + المنافسة من Google Keyword Planner
-- (Google Ads API: KeywordPlanIdeaService.GenerateKeywordIdeas)
-- مكمّل لـ Google Trends (الذي يعطي شعبية نسبية فقط، بلا أرقام مطلقة).

ALTER TABLE seo_opportunity_keywords
    ADD COLUMN IF NOT EXISTS avg_monthly_searches INTEGER,          -- متوسط البحث الشهري (أرقام نطاقية بدون صرف إعلاني)
    ADD COLUMN IF NOT EXISTS competition           TEXT,            -- LOW | MEDIUM | HIGH | UNSPECIFIED
    ADD COLUMN IF NOT EXISTS kw_volume_checked_at  TIMESTAMPTZ;     -- آخر جلب من Keyword Planner

-- ترتيب الفرص حسب حجم البحث الفعلي (الأعلى طلباً أولاً)
CREATE INDEX IF NOT EXISTS idx_seo_opp_volume
    ON seo_opportunity_keywords (active, avg_monthly_searches DESC NULLS LAST);
