-- ════════════════════════════════════════════════════════════════════════════
-- Migration 026: web_users — PDPL + email verify + copy throttle + Telegram link
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف:
--   1. consent_at TIMESTAMPTZ        : وقت موافقة PDPL (إلزامي قانونياً)
--   2. email_verified_at TIMESTAMPTZ : وقت تأكيد الإيميل (NULL = غير مؤكّد)
--   3. last_copy_at TIMESTAMPTZ      : آخر نسخ كوبون — لـ throttle anti-abuse
--   4. telegram_username TEXT        : ربط هوية الويب بهوية تيليجرام (للتحليل
--                                       الموحّد عبر web + bot + miniapp)
--   5. email_verification_codes      : جدول كودات تأكيد الإيميل (6 أرقام)
--
-- لماذا:
--   - consent_at         : PDPL يلزم بالموافقة الصريحة. غرامة محتملة 5م ريال.
--   - email_verified_at  : رفع جودة قاعدة الإيميلات + إشارة للبراندات.
--   - last_copy_at       : يمنع scraping الأكواد (حد 30 ثانية بين النسختين).
--   - telegram_username  : JOIN على bot_users.username يعطي بطاقة موحّدة
--                          (نشاط ويب + بوت + ميني-ويب لنفس الشخص).
-- ════════════════════════════════════════════════════════════════════════════

-- ─── 1. أعمدة جديدة على web_users ─────────────────────────────────────────
ALTER TABLE web_users
    ADD COLUMN IF NOT EXISTS consent_at         TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS email_verified_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_copy_at       TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS telegram_username  TEXT;

-- ─── 2. تعليقات توضيحية ───────────────────────────────────────────────────
COMMENT ON COLUMN web_users.consent_at        IS 'وقت موافقة PDPL على سياسة الخصوصية. NULL = لم يوافق بعد.';
COMMENT ON COLUMN web_users.email_verified_at IS 'وقت تأكيد المستخدم لإيميله عبر كود 6 أرقام.';
COMMENT ON COLUMN web_users.last_copy_at      IS 'آخر مرة نسخ المستخدم كوبوناً — لـ throttle 30s.';
COMMENT ON COLUMN web_users.telegram_username IS 'اسم المستخدم في تيليجرام (بدون @، lowercase). يربط مع bot_users.username للتحليل الموحّد.';

-- ─── 3. CHECK constraint على شكل telegram_username (5-32 حرف، يبدأ بحرف) ─
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'web_users_telegram_username_format'
    ) THEN
        ALTER TABLE web_users
            ADD CONSTRAINT web_users_telegram_username_format
            CHECK (
                telegram_username IS NULL
                OR telegram_username ~ '^[a-z][a-z0-9_]{4,31}$'
            );
    END IF;
END $$;

-- ─── 4. UNIQUE index case-insensitive على telegram_username (NULL مسموح) ─
-- منع شخصين من ادّعاء نفس اسم تيليجرام. NULL لا يدخل في UNIQUE فيُسمح
-- بالعديد من الحسابات بدون تيليجرام.
CREATE UNIQUE INDEX IF NOT EXISTS idx_web_users_telegram_username_unique
    ON web_users (telegram_username)
    WHERE telegram_username IS NOT NULL;

-- ─── 5. index لـ email_verified (للبحث عن غير المؤكّدين) ─────────────────
CREATE INDEX IF NOT EXISTS idx_web_users_email_unverified
    ON web_users (id)
    WHERE email_verified_at IS NULL;

-- ─── 4. جدول كودات تأكيد الإيميل ──────────────────────────────────────────
-- مشابه لـ password_reset_tokens (migration_003)، فترة صلاحية 15 دقيقة.
CREATE TABLE IF NOT EXISTS email_verification_codes (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,
    code_hash   TEXT        NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    used        BOOLEAN     DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    request_ip  INET
);
CREATE INDEX IF NOT EXISTS idx_email_verify_user      ON email_verification_codes (user_id);
CREATE INDEX IF NOT EXISTS idx_email_verify_expires   ON email_verification_codes (expires_at);

-- ─── 5. (اختياري) Backfill consent_at للحسابات الموجودة ───────────────────
-- الحسابات السابقة سُجّلت قبل وجود الـ checkbox. خيارات:
--   (أ) اتركها NULL وألزم المستخدمين القدامى بالموافقة عند الدخول التالي.
--   (ب) سامحهم وعلّمهم كأنهم وافقوا (legacy grace).
-- اخترنا (أ) — أكثر دفاعاً قانونياً. الكود التطبيقي يتعامل مع NULL بـ modal
-- إجباري عند الدخول التالي. لو تبي (ب) شغّل الأمر التالي يدوياً:
--   UPDATE web_users SET consent_at = created_at WHERE consent_at IS NULL;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
