---
name: blog_naturaltouch_cluster
description: عنقود ناتشورال تاتش 16 مقالاً — master.id=74 كود M13 خصم 10%؛ متجر سعودي عطور/عناية بخطوط خاصة (ذا عود/مسك إلدورا/فيلفيت/كاليستا وغيرها)؛ كان عنده 42 صفحة /c/ ميتة الأداء بلا عنقود مدوّنة؛ تشخيص: سقف سلطة الدومين لا بق صفحة
metadata:
  node_type: memory
  type: project
---

**٢٠٢٦-٠٩-١١** — المالك سأل «ايش باقي من المتاجر ما سوينا له سيو؟» فحُدّد حيّاً: **بلومينغديلز (81)** صفر تماماً، **ناتشورال تاتش (74)** له ٤٢ صفحة `/c/` بس صفر عنقود مدوّنة. المالك: «لا تسوي بلومينغديلز، يهمني ناتشورال تاتش فقط الآن» ثم «سوهم كلهم» (تشخيص + تصحيح النبذة + عنقود).

## التشخيص أولاً (قبل أي بناء)

- `seo_landing_pages` (`master_id=74`): **٤٢ صفحة `published`**، كلها من ٣٠-٣١ أغسطس ٢٠٢٦. **الأداء شبه صفر**: أعلى صفحة نقرة واحدة/٧أيام، أغلبها ٠ نقرة و٠ ظهور، معظمها بلا ترتيب (`current_position IS NULL`).
- تحقّق تقني حيّ لصفحة عيّنة: **200، `index,follow`، canonical صحيح** — ليست معطوبة. صفحة المتجر تربط **٣٩ رابط `/c/`** إليها — **ليست يتيمة**.
- **الخلاصة: مو بق صفحة، سقف سلطة الدومين المعروف** ([[seo_indexation_status]] — 244+ «مكتشفة لم تُفهرس»، النمط نفسه: صفحات جديدة عمرها أسابيع تحت مركز ٤٠-٧٠ بلا باكلينك ذو قيمة). لا حاجة لإصلاح تقني إضافي.

## المتجر — ناتشورال تاتش (Natural Touch)

- `master.id=74` · `store_id='ناتشورال تاتش'` (صُحِّح سابقاً من «ناشيونال» — [[seo_verify_brand_transliteration]]) · `name_en='Natural Touch'` · `public_coupon='M13'` · خصم **10%** · `my_coupon='6%'` (عمولة بوستيني صحيحة) · `affiliate_link=ntshop.sa` · `store_tags={بشرة, تجميل, جمال وعناية شخصية, شعر, عطور, عود و بخور, هدايا}` · `source_platform='بوستيني'`.
- ⚠️ **بق حيّ لم يُلتقط بالمرة السابقة:** `store_bio` **لسّا يبدأ بـ«ناشيونال»** — التصحيح شمل `store_id` بس لا `store_bio`. **صُحِّح هذه الجلسة** (UPDATE عبر إذن صريح للعملية) إلى «ناتشورال تاتش متجر سعودي...».
- تحقّق كتالوج حيّ (WebFetch، لا افتراض): `ntshop.sa` — أقسام العناية بالجسم/البشرة/الشعر/المنزل/المكياج/الاسترخاء والتدليك/العطور/الاكسسوارات + جديدنا/تصفية/الهدايا. **خطوط خاصة مؤكّدة**: ذا عود، مسك إلدورا (لاحظ الإملاء الصحيح من الموقع الحيّ — بايو الـDB كتبها «إدورا» بلا لام)، فيلفيت، كاليستا، ذا ليدي، أمورا، ايرس، إيفوري (نسائي) + نو يور ليميتس، باتشولي مسك (رجالي). `sitemap_products.xml` ≈٣١٠ منتج.

## الـ16 مقالاً (`2d3059f` — بادئة `naturaltouch-`)

pillar `naturaltouch-guide-saudi` (فئة `جمال وعطور`).
عطور: `naturaltouch-perfumes-guide-saudi` · `naturaltouch-signature-collections-guide-saudi` (جدول الخطوط العشرة) · `naturaltouch-oud-bakhoor-guide-saudi` · `naturaltouch-fragrance-longevity-guide-saudi` (فئة `عطور وعود`).
عناية: `naturaltouch-body-care-guide-saudi` · `naturaltouch-skincare-guide-saudi` · `naturaltouch-hair-care-guide-saudi` · `naturaltouch-home-fragrance-guide-saudi` · `naturaltouch-makeup-guide-saudi` · `naturaltouch-massage-spa-guide-saudi` (إخلاء حمل + جروح) · `naturaltouch-accessories-guide-saudi` (فئة `جمال وعطور`).
عمليات: `naturaltouch-gifts-guide-saudi` · `naturaltouch-seasonal-offers-guide-saudi` (فئة `هدايا`) · `naturaltouch-new-arrivals-clearance-guide-saudi` · `naturaltouch-coupon-m13-how-to-use-saudi` (فئة `أدلّة التوفير`).

**صدق تجاري:** خط «ذا عود» أُطِّر كعطور/تركيبات عودية لا دهن عود طبيعي خام — فحص صريح في المقال (نفس درس [[blog_rasees_cluster]]: فضح أكواد/ادّعاءات النسب الوهمية، وهنا فضح افتراض «طبيعي» بلا دليل).

## de-orphan (هَبّان محايدان)

`best-saudi-online-stores-2026` (بند بعد قولدن فلورا) · `makeup-guide-beginners-saudi-arabia` (بند بعد النهدي).

## التحقّق

`esbuild --bundle` **EXIT=0** (قبل وبعد de-orphan) · ١٩٨٤ مقالاً إجمالاً · ١٦ ناتشورال تاتش بلا نقص · صفر مكرّر/مكسور/FAQ ملتصق/باكتيك مهرَّب.

## معلّق

- **بلومينغديلز (id=81)** يبقى صفر سيو تماماً — المالك رفضه صراحةً هذه الجلسة، لا تبدأ فيه بلا طلب جديد.
- تحقّق النشر الحيّ على فيرسيل + `blog_bridge --write` — جاريان وقت كتابة هذا الملف.

يكمّل [[blog_rasees_cluster]] · [[blog_beluar_cluster]] (نفس نمط بيت العطور السعودي بخطوط توقيع) · [[seo_verify_brand_transliteration]] (أصل مشكلة الاسم) · [[seo_indexation_status]] (سقف السلطة).
