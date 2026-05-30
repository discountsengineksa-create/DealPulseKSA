-- ════════════════════════════════════════════════════════════════════════════
-- Migration 024: User Demographics — gender + birth_date for web_users
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف بيانات ديموغرافية تُجمع عند التسجيل بالموقع:
--   - gender      : 'male' | 'female'  (CHECK constraint)
--   - birth_date  : DATE (يُحسب منه العمر بالـ AGE())
--
-- لماذا: لتمكين تحليل ديموغرافي (توزيع الجنس + الفئات العمرية) لقاعدة
--         المستخدمين، وعرضها في صفحة «تحليل المستخدمين» بالداشبورد، وأيضاً
--         لاستخدامها في عروض الشراكة للبراندات (شريحة الجمهور المستهدف).
--
-- التطبيق:
--   psql -U postgres -d discounts_engine -f migration_024_user_demographics.sql
-- ════════════════════════════════════════════════════════════════════════════

-- ─── 1. إضافة الأعمدة ─────────────────────────────────────────────────────
ALTER TABLE web_users
    ADD COLUMN IF NOT EXISTS gender     TEXT,
    ADD COLUMN IF NOT EXISTS birth_date DATE;

-- ─── 2. CHECK constraint للجنس (يقبل male/female أو NULL للسجلات القديمة) ─
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'web_users_gender_check'
    ) THEN
        ALTER TABLE web_users
            ADD CONSTRAINT web_users_gender_check
            CHECK (gender IS NULL OR gender IN ('male', 'female'));
    END IF;
END $$;

-- ─── 3. CHECK constraint لتاريخ الميلاد (سن منطقي: 10–100 سنة) ────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'web_users_birth_date_check'
    ) THEN
        ALTER TABLE web_users
            ADD CONSTRAINT web_users_birth_date_check
            CHECK (
                birth_date IS NULL
                OR (birth_date <= CURRENT_DATE - INTERVAL '10 years'
                    AND birth_date >= CURRENT_DATE - INTERVAL '100 years')
            );
    END IF;
END $$;

-- ─── 4. تعليقات توضيحية ───────────────────────────────────────────────────
COMMENT ON COLUMN web_users.gender     IS 'جنس المستخدم: male | female (NULL للسجلات قبل migration_024).';
COMMENT ON COLUMN web_users.birth_date IS 'تاريخ ميلاد المستخدم؛ العمر = AGE(birth_date).';

-- ─── 5. index لتسريع تجميعات التحليل الديموغرافي ─────────────────────────
CREATE INDEX IF NOT EXISTS idx_web_users_gender     ON web_users(gender)     WHERE gender IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_web_users_birth_date ON web_users(birth_date) WHERE birth_date IS NOT NULL;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- بعد هذه الـ migration:
--   web_users.gender      : NULLABLE TEXT (male|female فقط)
--   web_users.birth_date  : NULLABLE DATE (10–100 سنة)
--   حقلين جديدين في نموذج تسجيل الموقع
--   تحليل ديموغرافي متاح في «تحليل المستخدمين»
