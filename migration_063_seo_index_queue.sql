-- ════════════════════════════════════════════════════════════════════════════
-- Migration 063: قائمة الفهرسة — تتبّع روابط الموقع المُرسَلة يدوياً لفهرسة Google
-- ════════════════════════════════════════════════════════════════════════════
-- المشكلة التي يحلّها: الموقع جديد و~4 صفحات فقط مفهرسة من 400+. الفهرسة اليدوية
-- عبر «URL Inspection → Request Indexing» في Search Console هي أسرع طريق، لكنها
-- رابطاً رابطاً ومحدودة بحصة يومية. يحتاج المالك لوحة تقول له: «هذه الروابط لم
-- تُفهرَس بعد — انسخها وأرسلها». المصدر الكامل للروابط هو sitemap.xml الحيّ.
--
-- التصميم: هذا الجدول يخزّن فقط الروابط التي عالجها المالك (فُهرست / تُجوهلت).
-- «المعلّقة» تُشتقّ ديناميكياً = (روابط sitemap) ناقص (هذا الجدول). فأي رابط جديد
-- يدخل sitemap يظهر تلقائياً، وما يُعلَّم «تمّ» يختفي — بلا أي مزامنة يدوية.
--
-- status: 'indexed' = أُرسل للفهرسة · 'ignored' = صفحة لا نريد فهرستها (خصوصية/شروط)
--
-- التطبيق:  python api/run_migration.py migration_063_seo_index_queue.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS seo_index_queue (
    url        TEXT PRIMARY KEY,                       -- الرابط الكامل كما في sitemap
    status     TEXT NOT NULL DEFAULT 'indexed',        -- 'indexed' | 'ignored'
    marked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- استعلام الصفحة يحمّل كل المعالَجة لطرحها من sitemap → فهرس على status.
CREATE INDEX IF NOT EXISTS idx_seo_index_queue_status
    ON seo_index_queue (status);

COMMIT;
