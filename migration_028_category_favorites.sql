-- ════════════════════════════════════════════════════════════════════════════
-- Migration 028: user_favorites — توسعة لدعم مفضلة الأقسام (categories)
-- ════════════════════════════════════════════════════════════════════════════
-- يحوّل user_favorites من جدول مفضلة للمتاجر فقط إلى polymorphic SSOT يدعم:
--     kind = 'store'    → store_id     (موجود من migration_027)
--     kind = 'category' → category_name (جديد هنا)
--
-- لماذا polymorphic بدل جدول منفصل user_category_favorites:
--   - JOIN واحد على user_favorites يجلب كل مفضلة الشخص (متاجر + أقسام)
--   - تحليلات الداشبورد لا تحتاج UNION بين جدولين
--   - الـ trigger المستقبلي للـ push:
--       "كود جديد لمتجر X (قسمه أزياء) ⇒ ابعث لكل من فضّل X أو فضّل قسم أزياء"
--     يصبح استعلام واحد، ليس اثنين.
--   - last_notified_at يعمل لكلا النوعين بنفس المنطق.
--
-- صفر downtime — كل التغييرات additive + idempotent:
--   1. kind         : TEXT NOT NULL DEFAULT 'store'  (الصفوف القديمة تبقى 'store')
--   2. category_name: TEXT NULL                       (للأقسام فقط)
--   3. store_id     : يصبح NULL-able + CHECK يضمن مالك واحد + نوع واحد
--   4. unique indexes جديدة per-kind
--
-- التطبيق:
--   python api/run_migration.py migration_028_category_favorites.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. عمود kind (discriminator) ────────────────────────────────────────
ALTER TABLE user_favorites
    ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'store';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uf_kind_check'
    ) THEN
        ALTER TABLE user_favorites
            ADD CONSTRAINT uf_kind_check CHECK (kind IN ('store', 'category'));
    END IF;
END $$;

-- ─── 2. عمود category_name (للأقسام فقط) ──────────────────────────────────
ALTER TABLE user_favorites
    ADD COLUMN IF NOT EXISTS category_name TEXT;

-- ─── 3. تحويل store_id إلى NULL-able (شرط لتمرير صفوف الأقسام) ───────────
ALTER TABLE user_favorites
    ALTER COLUMN store_id DROP NOT NULL;

-- ─── 4. CHECK يضمن: مالك واحد + نوع واحد بالضبط ───────────────────────────
-- - قيد المالك من 027 يبقى كما هو (web أو telegram، لا كلاهما).
-- - قيد جديد: لو kind='store'    ⇒ store_id NOT NULL و category_name NULL
--             لو kind='category' ⇒ category_name NOT NULL و store_id NULL
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uf_kind_target_consistent'
    ) THEN
        ALTER TABLE user_favorites
            ADD CONSTRAINT uf_kind_target_consistent CHECK (
                (kind = 'store'    AND store_id IS NOT NULL AND category_name IS NULL)
                OR
                (kind = 'category' AND category_name IS NOT NULL AND store_id IS NULL)
            );
    END IF;
END $$;

-- ─── 5. تطبيع category_name (trim + lower-ish) ────────────────────────────
-- نمنع تكرارات مثل "  أزياء " vs "أزياء". لا نُجبر على lowercase لأن العربية
-- لا تميّز بين حالة الأحرف، لكن نقصّ المسافات الزائدة.
-- نطبّق ذلك على مستوى التطبيق (في endpoints) وليس DB trigger لتجنّب overhead.

-- ─── 6. Unique indexes جديدة per-kind ─────────────────────────────────────
-- شرح: indexes 027 القديمة (uf_web_unique, uf_tg_unique) مبنية على
-- (owner, store_id) WHERE owner IS NOT NULL — لا تشمل category_name، لذا
-- نحتاج indexes منفصلة للأقسام. لا تتعارض مع القديمة لأن partial WHERE مختلف.

CREATE UNIQUE INDEX IF NOT EXISTS uf_web_category_unique
    ON user_favorites (web_user_id, category_name)
    WHERE web_user_id IS NOT NULL AND kind = 'category';

CREATE UNIQUE INDEX IF NOT EXISTS uf_tg_category_unique
    ON user_favorites (telegram_id, category_name)
    WHERE telegram_id IS NOT NULL AND kind = 'category';

-- ─── 7. index لقياس الأكثر تفضيلاً للأقسام (GROUP BY category_name) ───────
CREATE INDEX IF NOT EXISTS uf_category_idx
    ON user_favorites (category_name)
    WHERE kind = 'category';

-- ─── 8. تعليقات توضيحية ───────────────────────────────────────────────────
COMMENT ON COLUMN user_favorites.kind          IS 'نوع المفضّل: store (متجر) | category (قسم). تم إضافته في migration_028.';
COMMENT ON COLUMN user_favorites.category_name IS 'اسم القسم العربي (من master.store_tags). مطلوب لو kind=''category''. NULL لو kind=''store''.';
COMMENT ON COLUMN user_favorites.store_id      IS 'معرّف المتجر — مطلوب لو kind=''store''. NULL لو kind=''category''.';

COMMIT;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق سريع بعد التطبيق:
--   SELECT kind, COUNT(*) FROM user_favorites GROUP BY kind;
--   -- الصفوف القديمة كلها 'store' (الافتراضي).
--
--   -- جرّب إضافة قسم مفضّل تجريبياً:
--   INSERT INTO user_favorites (kind, telegram_id, category_name, platform)
--   VALUES ('category', 123456789, 'أزياء', 'bot');
--
--   -- لوحة الأكثر تفضيلاً للأقسام:
--   SELECT category_name, COUNT(*) people
--   FROM user_favorites WHERE kind='category'
--   GROUP BY category_name ORDER BY people DESC LIMIT 10;
