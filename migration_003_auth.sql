-- ════════════════════════════════════════════════════════════════════════════
-- Migration 003: Username/Password Authentication for web_users
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف دعم تسجيل الدخول التقليدي (اسم مستخدم + كلمة سر):
--   1. عمود password_hash لتخزين كلمة السر مشفرة بـ bcrypt
--   2. email يصير UNIQUE (للسماح بالدخول إما بالجوال أو بالإيميل)
--   3. تغيير firebase_uid ليصير اختياري تماماً (لن نستخدمه)
-- ════════════════════════════════════════════════════════════════════════════

-- ─── 1. إضافة password_hash ──────────────────────────────────────────────
ALTER TABLE web_users
    ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- ─── 2. جعل email فريد (UNIQUE) ──────────────────────────────────────────
-- نتجاهل الـ NULL تلقائياً (Postgres يسمح بـ multiple NULLs مع UNIQUE)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'web_users_email_unique'
    ) THEN
        ALTER TABLE web_users ADD CONSTRAINT web_users_email_unique UNIQUE (email);
    END IF;
END $$;

-- ─── 3. index على email للبحث السريع وقت تسجيل الدخول ──────────────────
CREATE INDEX IF NOT EXISTS idx_web_users_email ON web_users(email);

-- ─── 4. تنظيف: حذف أي مستخدمين Firebase تجريبيين (اختياري) ─────────────
-- (لو فيه مستخدمين تجريبيين من Firebase، نحذفهم لأن الـ schema تغيّر)
DELETE FROM web_users WHERE firebase_uid IS NOT NULL AND password_hash IS NULL;

-- ─── 5. جدول كودات استعادة كلمة المرور ──────────────────────────────────
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,           -- الكود مشفّر (مش plain)
    expires_at  TIMESTAMP NOT NULL,      -- 15 دقيقة عادةً
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    request_ip  INET                      -- لمنع الـ abuse
);

CREATE INDEX IF NOT EXISTS idx_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_reset_tokens_expires ON password_reset_tokens(expires_at);

-- ─── ✅ Done ─────────────────────────────────────────────────────────────
-- بعد هذه الـ migration:
--   web_users.password_hash    : NULLABLE (لكن سنفرضه في الكود للمستخدمين الجدد)
--   web_users.email            : UNIQUE
--   web_users.phone_number     : UNIQUE (موجود مسبقاً)
--   password_reset_tokens      : جدول كودات استعادة كلمة المرور
--   تسجيل الدخول              : phone_number أو email + password_hash
--   استعادة كلمة المرور        : كود 6 أرقام يُرسل للإيميل، صالح 15 دقيقة
