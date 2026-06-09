-- ════════════════════════════════════════════════════════════════════════════
-- Migration 044: شرائح الستوري المتعدّدة لكل متجر (story_slides)
-- ════════════════════════════════════════════════════════════════════════════
-- يحوّل «ستوري واحدة/متجر» (master.story_media_url) إلى «عدة ستوري/متجر»:
--   • كل متجر يمكن أن يملك عدّة شرائح (فيديو/صورة) تُعرض بالتتابع كقصص.
--   • العضوية في صف الستوري تبقى عبر is_promoted (نفس السابق).
--   • التحليلات (story_views) تبقى مجمّعة باسم المتجر (store_id) — بلا تغيير.
--
-- نُرحّل قيم master.story_media_url الموجودة إلى شريحة واحدة لكل متجر،
-- ونُبقي العمود القديم (دورمنت) لتفادي أي كسر — يُهمَل من الـ API.
--
-- صفر downtime — additive + idempotent.
-- التطبيق:  python api/run_migration.py migration_044_story_slides.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS story_slides (
    id          BIGSERIAL   PRIMARY KEY,
    master_id   INTEGER     NOT NULL REFERENCES master(id) ON DELETE CASCADE,
    media_url   TEXT        NOT NULL,
    sort_order  INTEGER     NOT NULL DEFAULT 0,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_story_slides_master
    ON story_slides (master_id, is_active, sort_order, id);

COMMENT ON TABLE story_slides IS
    'شرائح ستوري المتاجر — عدة فيديو/صورة لكل متجر، تُعرض بالتتابع. '
    'العضوية في الصف عبر master.is_promoted؛ التحليلات عبر story_views (باسم المتجر).';

-- ترحيل العمود القديم → شريحة واحدة لكل متجر يملك قيمة (idempotent)
INSERT INTO story_slides (master_id, media_url, sort_order, is_active)
SELECT m.id, m.story_media_url, 0, TRUE
FROM master m
WHERE m.story_media_url IS NOT NULL AND m.story_media_url <> ''
  AND NOT EXISTS (SELECT 1 FROM story_slides s WHERE s.master_id = m.id);

COMMIT;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق:
--   SELECT to_regclass('public.story_slides');
--   SELECT master_id, count(*) FROM story_slides GROUP BY master_id;
