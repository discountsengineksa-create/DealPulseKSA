-- ════════════════════════════════════════════════════════════════════════════
-- Migration 045: إنقاذ بقايا story_media_url وتقاعد العمود القديم
-- ════════════════════════════════════════════════════════════════════════════
-- بعد التحوّل إلى story_slides (migration 044)، بقي عمود master.story_media_url
-- يستقبل رفعات «الصفحة القديمة» أثناء انتقال النشر، والـ API يقرأ story_slides فقط
-- → ظهرت رفعات «مختفية». هذا الترحيل:
--   1. يُنقذ أي قيمة متبقّية في story_media_url إلى شريحة مستقلة (إن لم تكن ممثَّلة).
--   2. يُفرّغ العمود القديم نهائياً (NULL) حتى لا يصير فخّاً مستقبلاً.
-- العمود يبقى موجوداً (deprecated) لتفادي أي كسر؛ لم يعد يُكتب ولا يُقرأ.
--
-- idempotent — NOT EXISTS guard + العمود يصبح فارغاً بعد التشغيل.
-- التطبيق:  python api/run_migration.py migration_045_story_media_retire.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- 1) أنقذ كل قيمة لم تُمثَّل بعد كشريحة
INSERT INTO story_slides (master_id, media_url, sort_order, is_active)
SELECT m.id, m.story_media_url,
       COALESCE((SELECT MAX(s.sort_order) + 1 FROM story_slides s WHERE s.master_id = m.id), 0),
       TRUE
FROM master m
WHERE m.story_media_url IS NOT NULL AND m.story_media_url <> ''
  AND NOT EXISTS (
      SELECT 1 FROM story_slides s
      WHERE s.master_id = m.id AND s.media_url = m.story_media_url);

-- 2) تقاعد العمود القديم — تفريغ نهائي
UPDATE master SET story_media_url = NULL WHERE story_media_url IS NOT NULL;

COMMENT ON COLUMN master.story_media_url IS
    'DEPRECATED (migration 045): استُبدل بجدول story_slides. لا يُكتب ولا يُقرأ.';

COMMIT;
