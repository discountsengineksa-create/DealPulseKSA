-- ════════════════════════════════════════════════════════════════════════════
-- Migration 034: snapshot للترند والمروّجة داخل story_views
-- ════════════════════════════════════════════════════════════════════════════
-- المشكلة: تحليلات الستوري كانت تفلتر الترند بقراءة master.is_trending وقت
-- عرض اللوحة — وهي الحالة الحالية، مش الحالة لحظة فتح الستوري.
-- لو المتجر كان ترند يوم الإثنين وشاف العميل الستوري، ثم رجع لعادي يوم الجمعة،
-- السجل بيقول «عادي» مع إن العميل فعلياً شاف نسخة ترند.
--
-- الحل: نلتقط snapshot لحظة الـ INSERT لـ:
--   - was_promoted  ← master.is_promoted   (هل ظهر في صف الستوري أصلاً)
--   - was_trending  ← (master.is_trending = 'ترند 🔥')  (هل كان ناري لحظتها)
--
-- السجلات القديمة قبل هذا الـ migration: NULL في كلا العمودين — يُعالَج في
-- dashboard.py بسقوط احتياطي على master.is_trending مع caption يوضّح ذلك.
--
-- التطبيق: python api/run_migration.py migration_034_story_views_snapshot.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE story_views
    ADD COLUMN IF NOT EXISTS was_promoted BOOLEAN,
    ADD COLUMN IF NOT EXISTS was_trending BOOLEAN;

COMMENT ON COLUMN story_views.was_promoted IS
    'snapshot لـ master.is_promoted لحظة فتح الستوري. NULL = صف قديم قبل migration 034.';
COMMENT ON COLUMN story_views.was_trending IS
    'snapshot لـ (master.is_trending = ''ترند 🔥'') لحظة فتح الستوري. NULL = صف قديم قبل migration 034.';

-- index لفلترة الترند بسرعة في تحليلات الستوري
CREATE INDEX IF NOT EXISTS idx_story_views_was_trending
    ON story_views (was_trending, viewed_at DESC)
    WHERE was_trending IS NOT NULL;

COMMIT;

-- ─── ✅ تحقّق ──────────────────────────────────────────────────────────────
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name='story_views' AND column_name IN ('was_promoted','was_trending');
-- SELECT COUNT(*) FILTER (WHERE was_trending IS NULL) AS legacy_rows,
--        COUNT(*) FILTER (WHERE was_trending IS NOT NULL) AS new_rows
--   FROM story_views;
