-- ============================================================
-- Migration 001: إضافة user_id إلى action_logs
-- ------------------------------------------------------------
-- الهدف: تتبّع المستخدم لكل حركة (Action) بشكل مباشر بدلاً من
--        استخراجه من حقل details النصي.
-- آمن للتشغيل أكثر من مرة (idempotent) بفضل IF NOT EXISTS.
-- ============================================================

-- 1. إضافة العمود (nullable لأن الصفوف القديمة بدون user_id)
ALTER TABLE action_logs
    ADD COLUMN IF NOT EXISTS user_id BIGINT;

-- 2. فهارس تسريع: per-user analytics + per-action_type queries
CREATE INDEX IF NOT EXISTS idx_action_logs_user_id
    ON action_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_action_logs_action_type
    ON action_logs(action_type);

-- 3. (اختياري) backfill من حقل details للسجلات القديمة
--    details بصيغة "user:12345" أو "user:12345;tag:..."
UPDATE action_logs
SET user_id = NULLIF(split_part(split_part(details, 'user:', 2), ';', 1), '')::BIGINT
WHERE user_id IS NULL
  AND details LIKE '%user:%';

-- نتيجة متوقعة:
-- ALTER TABLE
-- CREATE INDEX (×2)
-- UPDATE n  ← عدد الصفوف القديمة المُحدّثة
