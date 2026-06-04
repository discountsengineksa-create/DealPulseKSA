-- ════════════════════════════════════════════════════════════════════════════
-- Migration 031: bot_users.deleted_at — soft-delete للحسابات (PDPL)
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف عمود `deleted_at` على `bot_users` لدعم حق الحذف (right-to-be-forgotten)
-- في PDPL. soft-delete بدل hard-delete لسببين:
--   1. الحفاظ على السجل التاريخي في `action_logs` (FK غير مفروض، لكن البيانات
--      التحليلية تستفيد من القدرة على فصل النشاط بين «نشط/محذوف»).
--   2. الاسترجاع خلال 30 يوم لو الحذف بالخطأ (سياسة Recovery).
--
-- استخدام:
--   - Soft delete:   UPDATE bot_users SET deleted_at = NOW() WHERE telegram_id = ?
--   - الاستعلامات التحليلية:  WHERE deleted_at IS NULL  (مفلتر افتراضياً)
--   - الحذف الفعلي بعد 30 يوم: cron job يعمل DELETE حسب deleted_at + interval
--
-- ملاحظة: نظير العمود موجود مسبقاً في `tests/setup_test_db.py` (مع تعليق
-- "PDPL (migration_017)"). لكن migration_017 الفعلي يخص social_responses
-- فقط ولم ينقل العمود إلى الإنتاج. هذا الـ migration يصحّح هذه الفجوة.
--
-- صفر downtime — التغييرات additive + idempotent.
-- التطبيق:  python api/run_migration.py migration_031_bot_users_soft_delete.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. إضافة العمود ──────────────────────────────────────────────────────
ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN bot_users.deleted_at IS
    'وقت soft-delete للحساب (PDPL right-to-be-forgotten). NULL = نشط، NOT NULL = محذوف. الحذف الفعلي بعد 30 يوماً عبر cron.';

-- ─── 2. partial index — يسرّع كل الاستعلامات التحليلية ───────────────────
-- كل KPI / segment / audience query يفلتر deleted_at IS NULL أولاً، فبدل
-- مسح كل bot_users لكل query، يقفز Postgres مباشرة لصفوف النشطين.
CREATE INDEX IF NOT EXISTS idx_bot_users_active
    ON bot_users (telegram_id)
    WHERE deleted_at IS NULL;

-- ─── 3. index على المحذوفين (للـ cron الذي يحذف نهائياً بعد 30 يوم) ──────
CREATE INDEX IF NOT EXISTS idx_bot_users_pending_purge
    ON bot_users (deleted_at)
    WHERE deleted_at IS NOT NULL;

COMMIT;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق سريع:
--   SELECT column_name FROM information_schema.columns
--       WHERE table_name='bot_users' AND column_name='deleted_at';
--   SELECT indexname FROM pg_indexes
--       WHERE tablename='bot_users' AND indexname LIKE 'idx_bot_users_%';
--   -- المتوقع: deleted_at موجود + indexان نشطان.
