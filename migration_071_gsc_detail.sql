-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 071 — تفصيل Search Console بالصفحة والاستعلام
--
-- لماذا: `seo_perf_snapshots` يخزّن **إجماليات الموقع** فقط، فلا تستطيع حملةٌ أن
-- ترى أداء **صفحتها المقصودة** ولا الاستعلامات التي جلبتها. هذان الجدولان يسدّان
-- ذلك، فتقرأ صفحة «🎯 إدارة الحملات» أرقام صفحتها لا أرقام الموقع كلّه.
--
-- ⚠️ **قاعدة قراءة إلزامية:** كل صفّ هنا — كما في `seo_perf_snapshots` — هو إجمالي
-- **نافذة ٢٨ يوماً منتهية بـ`snapshot_date`**، لا يومٌ واحد. **جمع الصفوف يضخّم
-- الرقم بعدد اللقطات** (وقع فعلاً: ٤٬٢٩٠ نقرة بدل ٢٤٨ — تضخيم ١٧٫٣ ضعفاً).
-- تُقرأ **آخر لقطة**، والصفوف الأقدم تُقرأ **اتجاهاً** لا مجموعاً.
--
-- آمنة للإعادة (IF NOT EXISTS في كل عبارة).
-- ═══════════════════════════════════════════════════════════════════════════

-- أداء كل صفحة (نافذة ٢٨ يوماً منتهية بـ snapshot_date)
CREATE TABLE IF NOT EXISTS seo_gsc_pages (
    snapshot_date DATE        NOT NULL,
    page          TEXT        NOT NULL,
    clicks        INTEGER     NOT NULL DEFAULT 0,
    impressions   INTEGER     NOT NULL DEFAULT 0,
    ctr           NUMERIC,
    position      NUMERIC,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_date, page)
);

CREATE INDEX IF NOT EXISTS idx_gsc_pages_page ON seo_gsc_pages (page, snapshot_date DESC);

-- أداء كل استعلام (نافذة ٢٨ يوماً منتهية بـ snapshot_date)
CREATE TABLE IF NOT EXISTS seo_gsc_queries (
    snapshot_date DATE        NOT NULL,
    query         TEXT        NOT NULL,
    clicks        INTEGER     NOT NULL DEFAULT 0,
    impressions   INTEGER     NOT NULL DEFAULT 0,
    ctr           NUMERIC,
    position      NUMERIC,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (snapshot_date, query)
);

CREATE INDEX IF NOT EXISTS idx_gsc_queries_clicks
    ON seo_gsc_queries (snapshot_date DESC, clicks DESC);
