---
name: blog_aldakheel_cluster
description: عنقود الدخيل للعود ٢٠٢٦-٠٩-٠٨ — ١٦ مقالاً بادئة aldakheel- (web 15a3d29)؛ master.id=83 كود HH14 خصم ٥٪ إضافي بوستيني؛ صفحات /c/ لا تُصنع؛ blog_bridge نُفِّذ ٢٠٢٦-٠٩-٠٩ (1545 صفّاً)
metadata:
  node_type: memory
  type: project
  originSessionId: 301bf35c-b513-43cd-9fe8-fd10f9839577
  modified: 2026-09-09
---

**٢٠٢٦-٠٩-٠٨** — المالك أرسل لقطات sa.aldakheeloud.com (صفحة إعلانات جوجل + الميغا-مينيو
+ صفحات فئات) وطلب «سو السيو حقه كامل ولا تنسى الروابط الداخليه». المتجر كان أُضيف
للكتالوج قبله بيوم (`first_time=2026-09-07`).

## المتجر — `master.id=83`

- `store_id='الدخيل للعود'` — تعريب صحيح (Autocomplete سعودي غنيّ: الرياض/عروض/فروع/
  عطور/توزيعات + **`كود خصم الدخيل للعود 2026/جديد/اول طلب`** = طلب كوبون حقيقي لا ملاحي فقط).
- كود `HH14` خصم **٥٪ إضافي يُحسب فوق عروض الموقع** · `my_coupon='6%'` (عمولتنا، نفس نمط
  الماجد/FNP لا كود تتبّع) · `source_platform='بوستيني'` · `last_time=2027-01-31`.
- `store_tags={عود و بخور,عطور,هدايا}` · `seo_enabled=True` · شحن مجاني فوق ٢٥٠ ريال ·
  دفع عند الاستلام · تقسيط تابي/تمارا · توصيل السعودية + الخليج.
- ⚠️ `affiliate_link` رابط فئة عميق (`sa.aldakheeloud.com/ar/عروض-خاصة/c1378565741...`)
  لا نطاق نظيف — **لم يُغيَّر** (كتابة DB، إذن المالك). الأكواد قبل روابط التتبّع → راجع مع المالك.
- عطور بأسماء لها طلب مستقل: سكاي · فزاع · امارينا · روزي/روز · راكز (العنابي/كراميل/
  الأزرق) · كراون (الأحمر/الفضي/الذهبي/الأبيض/الأسود/البني — أغنى ذيل) · أوسكار (فضي/ذهبي) ·
  ساري · نوار · لبان.

## التحقّق (صفر فبركة)

`sa.aldakheeloud.com/sitemap.xml` → `store.aldakheeloud.com/ar/sitemap-{1,2}.xml` **مقروء
بـcurl عادي** (لا Cloudflare عكس الماجد/ماكس/بوما). **٢٣١ منتجاً + كل الأقسام محقّقة**:
المبثوث والمعجون · مخلط · عطور النيش الفاخرة · أوسكار · معمول بخور · دهن العود · كراون ·
راكز · ابيك · العرين · ستورم · المسك · معطرات المنزل/الجسم · التوزيعات · مجموعات الهدايا.
صفر سعر رقمي مخترع، صفر هرم نفحات لأي إصدار (الألوان تسميات تجارية لا وصف رائحة — قيلت صراحةً).
«من ٩٦ ريال» مقتبَس من بانر عروض اليوم الوطني في لقطة المالك.

## العنقود — ١٦ مقالاً `aldakheel-` (web `15a3d29`، فئة «عود وبخور» = slug `oud`)

hub `aldakheel-guide-saudi` · `aldakheel-coupon-hh14-saudi` · `aldakheel-mens-perfumes-guide-saudi` ·
`aldakheel-womens-perfumes-guide-saudi` · `aldakheel-signature-perfumes-sky-rosy-saudi` ·
`aldakheel-crown-collection-guide-saudi` · `aldakheel-rakiz-perfumes-guide-saudi` ·
`aldakheel-oscar-collection-guide-saudi` · `aldakheel-niche-storm-abeek-areen-guide-saudi` ·
`aldakheel-hair-body-mist-guide-saudi` · `aldakheel-dahn-oud-guide-saudi` ·
`aldakheel-oud-bakhoor-mabthoth-guide-saudi` · `aldakheel-mukhalat-oils-musk-guide-saudi` ·
`aldakheel-home-fragrance-guide-saudi` · `aldakheel-gifts-tawzeeat-occasions-saudi` ·
`aldakheel-national-day-offers-saudi`.

**الزاوية:** بيت عطور سعودي تجاري + معطّرات منزل + توزيعات — متمايز عن الماجد (يملك تعليم
المبسوس/المعمول/الدخون) وعود رويال (العود الطبيعي/الدهن) وعبدالصمد القرشي (خطوط تراثية).
**قرار مكافحة التكاذُب ([[feedback_never_publish_competing_codes]] · [[blog_almajed_cluster]]):**
لم تُلمس عناقيد `almajed-*`/`oudroyal-*`/`asq-*`. أكواد المنافسين (AR196/HIIPP/ADM63)
**لا تظهر داخل أي مقال `aldakheel-`** — فقط في المقال المحايد `mabsous-vs-maamoul-vs-dukhoon-saudi`
(نقطة التقاطع المعتمدة، كل الأكواد مجموعة).

## de-orphan (نفس درس [[blog_fnp_cluster]])

أُضيف سطر الدخيل + روابط في: `best-saudi-online-stores-2026` (قسم عود وعطور — وأُضيف الماجد
أيضاً، كان ناقصاً) · `oud-bukhoor-guide-saudi-arabia` (قائمة المتاجر + قسم أكواد الخصم) ·
`mabsous-vs-maamoul-vs-dukhoon-saudi` (قائمة المتاجر + سطر الأكواد).

## التحقّق

`npx esbuild lib/blog.ts --bundle` **EXIT=0** · `tsc --noEmit` على blog.ts **EXIT=0** ·
صفر ```` ``` ````/`${` في كتلة aldakheel · **٦١ رابط `/store/` كلها `الدخيل للعود` مُرمَّزة صحيحاً** ·
صفر رابط `/blog/` مكسور · كل مقال: إفصاح أفلييت + جدول + FAQ (`**سؤال**`) + ١٤–١٩ رابطاً داخلياً.
عدّاد slug 1739→1755 (+16).

## صفحات /c/ — ⛔ لا تُصنع بمايقريشن ولا بأنبوب تلقائي

`migration_077` (٤ صفحات هبوط يدوية لـ id=83) **حُذف ٢٠٢٦-٠٩-٠٩** — المالك رفض النمط:
«مستحيل أسوّي مايقريشن على كل مقال؟». وأُزيل أنبوب التوليد التلقائي بالكامل
([[seo_page_portfolio_verdict]] §٢٠٢٦-٠٩-٠٩).

**الطريق الوحيد الآن (يدوي):** داشبورد → «🔍 محرّك صفحات SEO» → «✨ توليد صفحات حول
موضوع» (`/admin/seo-seed-custom`، المالك يكتب موضوعاً) → «توليد المسودّات» → مراجعة → نشر.
**صفر SQL، صفر مايقريشن، صفر كرون.** صفحات id=83 **لم تُصنع** — تُترك للمالك متى شاء.

- **`blog_bridge --write`** — **نُفِّذ ٢٠٢٦-٠٩-٠٩ (المالك)** ضمن إعادة بناء واحدة مع نايس:
  `blog_bridge` = **1545 صفّاً / 69 متجراً**، `aldakheel-` 16 صفّاً. → [[search_intelligence_layer]]
- **إعادة الفهرسة:** بعد نزول Vercel، ادفع الـ١٦ رابطاً + الهَبَّين المحدَّثين +
  `/store/الدخيل للعود` إلى `api.dealpulseksa.com/api/v1/admin/reindex-urls` **بعد ٢٠٠**
  ([[seo_bulk_reindex_ops]] · قاعدة نزيه).

## الحالة الاستراتيجية

الدخيل للعود **من المتاجر القليلة بطلب كوبون سعودي حقيقي** في دفعات ٢٠٢٦ (مثل مودانيسا/FNP،
عكس ماكس/بوما الملاحية) — «كود خصم الدخيل للعود» + أسماء العطور المفردة autocomplete غنيّ.
لكن السقف يبقى سلطة الدومين ([[seo_indexation_status]]) — القيمة موزّعة على الاستشهاد الذكي
+ تمرير سلطة `/store` + نقرات جوجل بعيدة. → [[ai_citation_channel]] · [[seo_page_portfolio_verdict]]

يكمّل [[blog_fnp_cluster]] · [[blog_almajed_cluster]] · [[voice_bible]] ·
[[content_guardrails_playbook]] · [[feedback_verify_catalog_before_claim]] ·
[[seo_verify_brand_transliteration]] · [[boostiny_publisher_channel]].
