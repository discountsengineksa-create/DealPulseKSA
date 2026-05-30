-- ════════════════════════════════════════════════════════════════════════════
-- Migration 025: Re-add gender + birth_date to bot_users (via mini-web modal)
-- ════════════════════════════════════════════════════════════════════════════
-- يُعيد العمودين اللذين كانا في bot_users سابقاً، لكن هذه المرة:
--   ✅ بقيم مُعطاة صراحةً من المستخدم (موديال إلزامي في الميني-ويب)
--   ✅ مع CHECK constraints (يطابق web_users — migration_024)
--   ❌ لا تخمين، لا استنتاج
--
-- مهم: داخل deal_pulse_bot.py توجد دالة clean_legacy_columns() كانت تحذف
-- birth_date في كل إقلاع للبوت. أُزيلت في commit مرافق لهذه الـ migration
-- — وإلا سيُحذف العمود ثانية عند بدء البوت.
--
-- التطبيق:
--   psql "$DATABASE_URL" -f migration_025_bot_users_demographics.sql
-- ════════════════════════════════════════════════════════════════════════════

-- ─── 1. إضافة الأعمدة ─────────────────────────────────────────────────────
ALTER TABLE bot_users
    ADD COLUMN IF NOT EXISTS gender     TEXT,
    ADD COLUMN IF NOT EXISTS birth_date DATE;

-- ─── 2. CHECK constraint للجنس ─────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bot_users_gender_check'
    ) THEN
        ALTER TABLE bot_users
            ADD CONSTRAINT bot_users_gender_check
            CHECK (gender IS NULL OR gender IN ('male', 'female'));
    END IF;
END $$;

-- ─── 3. CHECK constraint لتاريخ الميلاد (10–100 سنة) ──────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'bot_users_birth_date_check'
    ) THEN
        ALTER TABLE bot_users
            ADD CONSTRAINT bot_users_birth_date_check
            CHECK (
                birth_date IS NULL
                OR (birth_date <= CURRENT_DATE - INTERVAL '10 years'
                    AND birth_date >= CURRENT_DATE - INTERVAL '100 years')
            );
    END IF;
END $$;

-- ─── 4. تعليقات توضيحية ───────────────────────────────────────────────────
COMMENT ON COLUMN bot_users.gender     IS 'جنس المستخدم: male | female (يُجمع من موديال الميني-ويب).';
COMMENT ON COLUMN bot_users.birth_date IS 'تاريخ ميلاد المستخدم؛ العمر = AGE(birth_date).';

-- ─── 5. indexes للتحليل الديموغرافي ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bot_users_gender     ON bot_users(gender)     WHERE gender IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_bot_users_birth_date ON bot_users(birth_date) WHERE birth_date IS NOT NULL;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- بعد هذه الـ migration + إزالة DROP من clean_legacy_columns:
--   bot_users.gender      : NULLABLE TEXT (male|female)
--   bot_users.birth_date  : NULLABLE DATE (10–100 سنة)
--   موديال إلزامي في الميني-ويب يجمع القيمتين لكل مستخدم تيليجرام
