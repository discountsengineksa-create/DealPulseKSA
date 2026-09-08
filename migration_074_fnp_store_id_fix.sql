-- migration_074_fnp_store_id_fix.sql
-- تصحيح تعريب اسم فيرنز اند بيتل (FNP) قبل توليد SEO.
--
-- Why: أُضيف المتجر 2026-09-07 بـ store_id='فيرنز اند بيتلز'. Google Autocomplete
--   السعودي (gl=sa) يصحّح تلقائياً إلى «فيرنز اند بيتل» (بلا ز)، و«فرنز اند بتلز»
--   و«فيرنز ان بيتلز» = صفر اقتراح، بينما «كود خصم فيرنز اند بيتل» اقتراح حيّ.
--   store_id يبني /store/{الاسم} + H1 + مسار التنقّل + عنوان كل صفحات /c/، فاسمٌ
--   خاطئ = كل الأصول تستهدف كلمة صفرية الطلب. → seo_verify_brand_transliteration.md
--
-- النطاق: master (المصدر) + النسخة المكرّرة في social_posts_log. تُترك سجلّات
--   غير قابلة للتعديل: post_text (أرشيف منشور مُرسَل)، api_request_metrics.path
--   (سجلّ طلبات)، logo_url/social_poster_url (مفاتيح أصول Cloudinary تعمل مستقلّةً
--   عن الاسم). الإنجليزي name_en='Ferns N Petals' صحيح ولا يُلمَس.

BEGIN;

UPDATE master
SET store_id     = 'فيرنز اند بيتل',
    store_bio    = replace(store_bio,    'فيرنز اند بيتلز', 'فيرنز اند بيتل'),
    description  = replace(description,  'فيرنز اند بيتلز', 'فيرنز اند بيتل'),
    affiliate_link = 'https://www.fnp.sa'
WHERE id = 82;

UPDATE social_posts_log
SET store_id = 'فيرنز اند بيتل'
WHERE master_id = 82
  AND store_id = 'فيرنز اند بيتلز';

COMMIT;
