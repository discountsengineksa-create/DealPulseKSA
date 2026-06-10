-- migration_048_drop_dead_master_columns.sql
-- تنظيف الأساس (2026-06-10): حذف أعمدة master الراكدة/المكرّرة + الجدول الميت users_master.
--
-- خلفية: العدّادات الحيّة هي total_link_clicks / total_coupon_copies (يزيدها البوت+API).
-- الأعمدة أدناه قديمة، خارجة عن التزامن (ثبت اختلافها فعلياً)، ولا يقرأها أي كود حيّ
-- (تحقّقنا: البوت/الـAPI/الداشبورد/الموقع). تبقى my_coupon لأنها مُستخدَمة (كود تتبّع العمولة).
--
-- السلامة: ننسخ بيانات الأعمدة في جدول احتياطي قبل الحذف (قابلية رجوع بلا snapshot)،
-- والكل ضمن معاملة واحدة. idempotent عبر IF EXISTS.

BEGIN;

-- 0) حذف view ميت يعتمد على بعض الأعمدة الميتة (coupons_view = SELECT ... FROM master).
--    غير مستخدَم في أي كود (بوت/API/داشبورد/ويب) — تحقّقنا. v_social_leads لا يتأثّر.
--    (لإعادة إنشائه لو لزم مستقبلاً: SELECT * FROM master مع الأعمدة الحيّة فقط.)
DROP VIEW IF EXISTS coupons_view;

-- 1) نسخة احتياطية لبيانات الأعمدة الراكدة (للرجوع لو لزم).
--    محروسة بـ EXECUTE ديناميكي: تعمل فقط لو الأعمدة ما زالت موجودة → آمنة لإعادة التشغيل
--    (لو شُغّلت بعد الحذف لا تفشل على عمود غير موجود).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='master' AND column_name='link_clicks') THEN
    EXECUTE 'CREATE TABLE IF NOT EXISTS _deprecated_master_cols_bak_20260610 AS
             SELECT id, link_clicks, copy_clicks, click_count, total_clicks,
                    total_search_hits, performance_status, visit_categorie, target_category
             FROM master';
  END IF;
END $$;

-- 2) حذف الأعمدة الراكدة من master
ALTER TABLE master
  DROP COLUMN IF EXISTS link_clicks,
  DROP COLUMN IF EXISTS copy_clicks,
  DROP COLUMN IF EXISTS click_count,
  DROP COLUMN IF EXISTS total_clicks,
  DROP COLUMN IF EXISTS total_search_hits,
  DROP COLUMN IF EXISTS performance_status,
  DROP COLUMN IF EXISTS visit_categorie,
  DROP COLUMN IF EXISTS target_category;

-- 3) حذف الجدول الميت (فارغ، بلا مراجع كود، بلا FK)
DROP TABLE IF EXISTS users_master;

COMMIT;
