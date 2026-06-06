-- ════════════════════════════════════════════════════════════════════════════
-- Migration 037: تتبّع المحظورين على البوت + استبعاد تلقائي
-- ════════════════════════════════════════════════════════════════════════════
-- المشكلة: لو مستخدم حظر البوت أو حذف المحادثة → Telegram API يرجّع 403.
-- بدون تتبّع، نُحاول الإرسال له كل حملة ونحرق rate-limit + نلوّث الإحصاءات.
--
-- الحل: عمودان جديدان على bot_users:
--   • telegram_blocked_at  ← تاريخ أول 403 (NULL = ما حظر)
--   • last_telegram_error  ← نص آخر خطأ (للتشخيص)
--
-- محرّك الإرسال (audience_sender.py) يحدّث هذي الأعمدة تلقائياً عند 403،
-- ومحرّك الشرائح (audience_engine.py) يستبعد المحظورين من قناة تليجرام
-- تلقائياً (مع خيار apply_block_filter=False للتجاوز اليدوي).
--
-- التطبيق: python api/run_migration.py migration_037_telegram_blocked_tracking.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS telegram_blocked_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_telegram_error TEXT;

COMMENT ON COLUMN bot_users.telegram_blocked_at IS
    'تاريخ أول استجابة 403 من Telegram (المستخدم حظر البوت أو حذف المحادثة). NULL = نشط.';
COMMENT ON COLUMN bot_users.last_telegram_error IS
    'نص آخر خطأ من Telegram API (للتشخيص). يُحدَّث في كل محاولة فشل.';

-- index للاستبعاد السريع (يُستخدم في كل عدّ شريحة تليجرام)
CREATE INDEX IF NOT EXISTS idx_bot_users_active_telegram
    ON bot_users (telegram_id)
    WHERE telegram_blocked_at IS NULL AND deleted_at IS NULL;

COMMIT;

-- ─── ✅ تحقّق ──────────────────────────────────────────────────────────────
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name='bot_users' AND column_name IN ('telegram_blocked_at','last_telegram_error');
-- SELECT COUNT(*) FILTER (WHERE telegram_blocked_at IS NOT NULL) AS blocked,
--        COUNT(*) FILTER (WHERE telegram_blocked_at IS NULL)     AS active
--   FROM bot_users WHERE deleted_at IS NULL;
