-- migration_055: عمود إنجليزي لكتالوج الأقسام.
-- categories_tags كان عربياً فقط (tag_name)؛ نضيف tag_name_en ليصبح
-- الكتالوج زوجاً مرتبطاً (عربي↔إنجليزي) يُدار من صفحة «إدخال بيانات الماستر».
-- البوت والـAPI يقرآن tag_name/priority_rank فقط — إضافة العمود لا تكسرهما.
ALTER TABLE categories_tags ADD COLUMN IF NOT EXISTS tag_name_en text;
