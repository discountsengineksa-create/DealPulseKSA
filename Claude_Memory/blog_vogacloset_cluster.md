---
name: blog_vogacloset_cluster
description: عنقود فوغا كلوسيت — 15 مقالاً (3 لكل قسم: نسائي/رجالي/أطفال/جمال/منزل) بربط داخلي متبادل + هَب من الدلائل الرئيسية
type: project
originSessionId: 2c4140c0-93ed-4f3d-a056-c66643fc9860
---
**2026-07-09 — عنقود فوغا كلوسيت مكتمل، منشور، مربوط.**

## البنية

15 مقالاً في `dealpulseksa-web/lib/blog.ts` (commit 4b6de74)، 5 أقسام × 3 مقالات، كلها تحت الأقسام الحقيقية من موقع vogacloset.com (تحقّق مباشر):

- **نسائي:** `vogacloset-womens-fashion-guide-saudi` (هَب فرعي) · `vogacloset-womens-dresses-occasion-saudi` · `vogacloset-modest-abayas-jalabiyat-saudi`
- **رجالي:** `vogacloset-mens-fashion-guide-saudi` (هَب فرعي) · `vogacloset-mens-shoes-sneakers-saudi` · `vogacloset-mens-shirts-trousers-saudi`
- **أطفال:** `vogacloset-kids-fashion-guide-saudi` (هَب فرعي) · `vogacloset-kids-school-uniform-saudi` · `vogacloset-kids-occasion-gifts-saudi`
- **جمال:** `vogacloset-beauty-makeup-skincare-saudi` (هَب فرعي) · `vogacloset-perfumes-fragrances-saudi` · `vogacloset-haircare-kerastase-olaplex-saudi`
- **منزل:** `vogacloset-home-decor-guide-saudi` (هَب فرعي) · `vogacloset-bedroom-bathroom-essentials-saudi` · `vogacloset-home-accessories-decor-saudi`

## الربط الداخلي

- **من الهَب الرئيسي** (`online-shopping-savings-guide-saudi-arabia`): سطر جديد لعنقود فوغا في قسم «الأزياء والإطلالة» يشير للـ5 أقسام.
- **من `best-saudi-online-stores-2026`:** رابط فوغا عُدّل ليعرض العنقود الكامل.
- **بين المقالات:** كل مقال يشير لأخوته + هَب فرعي + `/store/فوغا كلوسيت` + `/calendar` + دلائل عامة + **إحالات لعنقود ذا ديل** (للأوت-لِت المصمّم) — يبني شبكة سلطة بين العنقودين.
- **متوسط الربط:** 9-13 رابطاً داخلياً/مقال.

## معلومات المتجر الحقيقية المستخدمة

- **name:** فوغا كلوسيت (VogaCloset) — Chalhoub-independent
- **الخلفية:** متجر بريطاني قاعدته الشرق الأوسط، 30,000+ قطعة، 400+ براند
- **الكود:** `6hj` — قسم التجميل مستثنى (سياسة المتجر — قد ينفع الاستثناء ينهي)
- **الخصومات:** 20-80٪ عدا التجميل
- **الأقسام (من الموقع مباشرة):** Women · Men · Kids · Beauty · Home
- **البراندات المؤكّدة:** Boohoo, PrettyLittleThing, Karen Millen, Coast Fashion, Club L London, Debenhams, La Redoute, Trendyol, BoohooMAN, Burton, Angel & Rocket, Puma, Makeup Revolution, Kerastase, Olaplex, Debenhams Beauty
- **الدفع:** Tabby, Tamara, Mada, COD, Visa, Mastercard, PayPal, Apple Pay
- **الشحن:** 3-7 أيام عمل للمدن الكبرى + COD متاح

## قيود التزمت بها

- صفر أسعار رقمية (وصفية فقط).
- إفصاح أفلييت أعلى كل مقال.
- تنبيهات YMYL في مقالات الجمال والعناية بالشعر.
- Kids articles: لا سلامة حرجة (لا مقاعد سيارة/وسائد رُضّع).
- Home articles: صريحة أن المتجر مكمّل لا رئيسي للأثاث؛ توجيه لـ سيدار/بيتي شوب/دليل الأثاث للاحتياج الأكبر.
- Bot device split respected (Fashion/Beauty/Kids/Home decor accessories — لم ألمس furniture-)
- 0 triple backticks و0 `${` داخل body.
- الصراحة عن استثناء التجميل من الكود (سياسة المتجر) — بدل ادّعاء التخفيض.

## نمط الرابط الشبكي مع ذا ديل

المقالات النسائية/الرجالية/الأطفال/الجمال تحوي **إحالة صريحة لعنقود ذا ديل** في قسم "متى تختارين X ومتى غيره" — يعطي القارئ خيار الترقية للفاخر ويبني ربطاً متبادلاً بين العنقودين.
