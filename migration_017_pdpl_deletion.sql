-- ============================================================================
-- Migration 017 — PDPL Soft Deletion (Saudi Personal Data Protection Law § 8)
-- ============================================================================
-- يضيف:
--   1. web_users.deleted_at   — timestamp الحذف الناعم (NULL = نشط)
--   2. bot_users.deleted_at   — مثله
--   3. مؤشرات partial للاستعلامات السريعة على الحسابات النشطة فقط
--   4. صف seed في pdpl_audit_log يوضّح بدء تفعيل النظام
--
-- نمط الحذف الناعم:
--   - DELETE /api/v1/users/me → SET deleted_at = NOW()
--   - الحساب يختفي فوراً من الواجهة (login/me يفشلان)
--   - بعد 30 يوماً worker يومي يمسحه نهائياً (hard delete cascade)
--   - في الـ grace period (30 يوم) يمكن للمستخدم الاسترجاع عبر cancel-deletion
--
-- لماذا soft delete؟
--   PDPL § 8 يسمح بفترة استبقاء معقولة لـ:
--   (أ) معالجة طلبات الاسترجاع الخاطئة
--   (ب) الالتزام بطلبات السلطات إن وُجدت
--   30 يوم هو السقف القانوني المعتاد.
--
-- العمليات الذرّية:
--   كل التغييرات داخل BEGIN/COMMIT — لو فشل أي جزء يُرجَع كل شيء.
-- ============================================================================

BEGIN;

-- 1) عمود deleted_at على web_users (مستخدمو الموقع)
ALTER TABLE web_users
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN web_users.deleted_at IS
    'PDPL soft-delete timestamp. NULL = نشط. != NULL = بانتظار الحذف النهائي بعد 30 يوماً.';

-- مؤشر partial: استعلامات auth.py تستفيد منه (WHERE deleted_at IS NULL)
CREATE INDEX IF NOT EXISTS idx_web_users_active
    ON web_users(id) WHERE deleted_at IS NULL;

-- مؤشر للـ worker الذي يبحث عن المنتهية فترتهم
CREATE INDEX IF NOT EXISTS idx_web_users_pending_purge
    ON web_users(deleted_at) WHERE deleted_at IS NOT NULL;


-- 2) عمود deleted_at على bot_users (مستخدمو تيليجرام)
ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN bot_users.deleted_at IS
    'PDPL soft-delete timestamp. NULL = نشط. الحذف عبر /delete_account في البوت.';

CREATE INDEX IF NOT EXISTS idx_bot_users_active
    ON bot_users(telegram_id) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_bot_users_pending_purge
    ON bot_users(deleted_at) WHERE deleted_at IS NOT NULL;


-- 3) سجل بدء تفعيل النظام في pdpl_audit_log (للأثر القانوني)
INSERT INTO pdpl_audit_log (actor, action, target, status, meta)
VALUES (
    'system',
    'pdpl_deletion_enabled',
    'migration_017',
    'ok',
    jsonb_build_object(
        'description', 'PDPL soft-deletion system activated',
        'grace_period_days', 30,
        'web_users_column', 'deleted_at',
        'bot_users_column', 'deleted_at'
    )
)
ON CONFLICT DO NOTHING;

COMMIT;
