-- migration_057: سماح/منع توليد SEO لكل متجر على حدة.
-- بعض المعلنين يمنعون SEO على اسم البراند (مثل AliExpress/Alibaba group —
-- حظر + عدم دفع). نُلغي توليد صفحات SEO لذلك المتجر بإلغاء هذا العلم.
-- TRUE (افتراضي) = يدخل التوليد اليومي؛ FALSE = مستثنى تماماً من SEO.
ALTER TABLE master ADD COLUMN IF NOT EXISTS seo_enabled boolean DEFAULT TRUE;
