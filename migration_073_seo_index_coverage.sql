-- ════════════════════════════════════════════════════════════════════════════
-- Migration 073: تغطية فهرسة Google لكل رابط — تشخيص من Search Console
-- ════════════════════════════════════════════════════════════════════════════
-- المشكلة التي يحلّها: صفحة «🔎 الفهرسة» تشتقّ «المعلّقة» = (روابط sitemap) ناقص
-- (seo_index_queue الذي يُملأ يدوياً رابطاً رابطاً). النتيجة ~1840 رابط «معلّق»
-- أغلبه مفهرَس أصلاً في Google — لا أحد يعرف أيّها، فيُعاد إرسال روابط مفهرسة
-- وتُهدر حصة Google Indexing (200/يوم).
--
-- الحل: هذا الجدول يخزّن حالة Google الحقيقية لكل رابط، تُملأ من مصدرين:
--   • impressions — أي رابط له ≥1 انطباع في GSC خلال 16 شهراً ⇒ مفهرَس قطعاً.
--   • inspection  — URL Inspection API لكل رابط لم يظهر بانطباع: يعطي coverageState
--                   الحقيقي (مفهرَس / مكتشف-لم-يُزحف / زُحف-ورُفض / مجهول لـ Google).
--
-- verdict (تصنيف مُجمَّع فوق coverage_state الخام):
--   indexed             — مفهرَس، لا إجراء (is_indexed = TRUE)
--   discovered          — «Discovered - currently not indexed» → الدفع يفيد (ميزانية زحف)
--   crawled_not_indexed — «Crawled - currently not indexed» → مشكلة جودة، الدفع لا يفيد
--   unknown             — «URL is unknown to Google» → لم يُكتشف بعد، أولوية دفع
--   excluded_other      — Duplicate / redirect / Excluded … → يعالجها canonical عادةً
--
-- التطبيق:  python api/run_migration.py migration_073_seo_index_coverage.sql
-- آمنة للإعادة (IF NOT EXISTS في كل عبارة).
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- تمييز مصدر صفوف قائمة الفهرسة: 'manual' = المالك ضغط «✓ فُهرست» · 'gsc' = مطابقة تلقائية
ALTER TABLE seo_index_queue
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';

CREATE TABLE IF NOT EXISTS seo_index_coverage (
    url            TEXT PRIMARY KEY,                    -- الرابط المطبَّع (unquote، بلا / أخيرة، بلا ?query)
    coverage_state TEXT,                                -- coverageState الخام من Google (نص إنجليزي)
    verdict        TEXT NOT NULL,                       -- indexed|discovered|crawled_not_indexed|unknown|excluded_other
    is_indexed     BOOLEAN NOT NULL DEFAULT FALSE,
    last_source    TEXT NOT NULL,                       -- impressions|inspection
    checked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_seo_index_coverage_verdict
    ON seo_index_coverage (verdict);

COMMIT;
