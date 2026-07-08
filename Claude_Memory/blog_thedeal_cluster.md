---
name: blog_thedeal_cluster
description: عنقود ذا ديل أوتلت — 15 مقالاً (3 لكل قسم: نسائي/رجالي/أطفال/جمال/مصمّمين) بربط داخلي متبادل + هَب من الدلائل الرئيسية
type: project
originSessionId: 2c4140c0-93ed-4f3d-a056-c66643fc9860
---
**2026-07-08 — عنقود ذا ديل أوتلت مكتمل، منشور، مربوط.**

## البنية

15 مقالاً في `dealpulseksa-web/lib/blog.ts` (commit 90935f8)، 5 أقسام × 3 مقالات، كلها تحت الأقسام الحقيقية من موقع thedealoutlet.com (تحقّق مباشر لا افتراض):

- **نسائي:** `thedeal-womens-designer-fashion-guide-saudi` (هَب فرعي) · `thedeal-womens-bags-shoes-outlet-saudi` · `thedeal-womens-occasion-dresses-saudi`
- **رجالي:** `thedeal-mens-designer-fashion-guide-saudi` (هَب فرعي) · `thedeal-mens-shoes-outlet-saudi` · `thedeal-mens-grooming-fragrances-saudi`
- **أطفال:** `thedeal-kids-designer-clothing-saudi` (هَب فرعي) · `thedeal-babies-designer-outlet-saudi` · `thedeal-kids-gifts-outlet-saudi`
- **جمال:** `thedeal-designer-perfumes-outlet-saudi` (هَب فرعي) · `thedeal-designer-makeup-skincare-saudi` · `thedeal-bath-body-outlet-saudi`
- **مصمّمون:** `thedeal-designers-outlet-brands-list-saudi` · `thedeal-outlet-concept-how-it-works` · `thedeal-outlet-vs-boutique-when-to-buy`

## الربط الداخلي (الأهمّ)

- **من الهَب الرئيسي** (`online-shopping-savings-guide-saudi-arabia`): سطر جديد لعنقود الأوت-لِت في قسم «الأزياء والإطلالة» يشير للـ5 أقسام + مقال «كيف يعمل الأوت-لِت».
- **من `best-saudi-online-stores-2026`:** رابط ذا ديل عُدّل ليعرض العنقود (نسائي/رجالي/أطفال/براندات).
- **بين المقالات نفسها:** كل مقال يشير لأخوته داخل قسمه + هَب فرعي + مقال «كيف يعمل الأوت-لِت» + `/store/ذا ديل` + `/calendar` + دلائل عامة (womens-fashion/mens-essentials/perfume/kids-shopping/footwear/gifts).
- **متوسط الربط:** 9-13 رابطاً داخلياً/مقال (وفق `content_guardrails_playbook`).

## معلومات المتجر الحقيقية المستخدمة

- **name:** ذا ديل أوتلت (The Deal Outlet)
- **الخلفية:** تابع لقسم التصفية في مجموعة الشلهوب (رائدة التجزئة الفاخرة بالشرق الأوسط)
- **الكود المعلن:** `FIRST15` — ١٥٪ على الطلب الأوّل من التطبيق
- **العرض الإضافي:** خصومات تصل ٧٥٪
- **الأقسام (من الموقع مباشرة):** Women · Men · Kids · Beauty · All Designers
- **البراندات المؤكّدة (لقطة من الموقع):** Adidas, BOSS, D&G, Etro, Farm Rio, Fila, Gucci, Guess, Hackett London, Hugo Boss, Jil Sander, Karl Lagerfeld, Lacoste, Maison Margiela, Michael Kors, New Balance, Salvatore Ferragamo, Solace London, Stella McCartney, Swarovski, Tory Burch, Tom Ford, Versace, Vilebrequin, Axel Arigato
- **الشحن:** thedealoutlet.com قاعدته إماراتية — كل مقال يذكّر الشحن الدولي للسعودية والجمارك المحتملة

## قيود التزمت بها

- صفر أسعار رقمية (وصفية فقط: خصومات وصلت ٧٥٪ — ذكر رسمي، لا اختراع).
- إفصاح أفلييت أعلى كل مقال.
- تنبيهات YMYL/جمال أدرجت في مقالات المكياج والباث (إرشادي لا نصيحة طبية).
- Kids articles ما لمست فئة السلامة الحرجة (مقاعد سيارة/وسائد رُضّع).
- Bot device split respected (Kids/Beauty/Fashion كلها من نصيبي؛ لم ألمس home-/toys/furniture).
- 0 triple backticks و0 `${` داخل body.

## نمط حلّ التعارض المتكرّر

الجهاز الآخر يدفع Alibaba clusters كل بضع دقائق. حصلت 3 تعارضات متتالية عند git pull --rebase — كلها بنفس النمط: كلاهما يُدخل قبل `];` فيتقاسمان `{` واحداً. الحلّ الآلي:

1. حذف `<<<<<<< HEAD` قبل أوّل post للفريق الآخر
2. بين آخر body للفريق الآخر و`=======`، أضف `},\n  {`
3. حذف `>>>>>>> <sha>` بعد آخر body لي (الـ`},` بعده يقفل آخر post صحيح)

## الرأي الصريح المُعلن قبل التنفيذ

أخبرت المالك أن العنق ليس نقص محتوى بل السلطة/الفهرسة (وفق `content_guardrails_playbook` الصراحة الاستراتيجية) — لكن نفّذت طلبه. الرافعة الأفضل الآن: طلب فهرسة GSC للـ15 مقالاً + باكلينكات على `/store/ذا ديل`.
