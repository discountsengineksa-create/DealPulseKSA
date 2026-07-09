---
name: blog_mamaspapas_cluster
description: عنقود ماماز آند باباز — 15 مقالاً (3 لكل قسم: عربات/غرفة أطفال/ملابس/تغذية/استحمام وهدايا) بمعايير سلامة صارمة
type: project
originSessionId: 2c4140c0-93ed-4f3d-a056-c66643fc9860
---
**2026-07-09 — عنقود ماماز آند باباز مكتمل، منشور، مربوط.**

## البنية

15 مقالاً في `dealpulseksa-web/lib/blog.ts` (commit 3bdb844)، 5 أقسام × 3 مقالات:

- **العربات:** `mamaspapas-strollers-guide-saudi` (هَب فرعي) · `mamaspapas-newborn-lightweight-strollers-saudi` · `mamaspapas-cabin-strollers-travel-accessories-saudi`
- **غرفة الأطفال:** `mamaspapas-nursery-furniture-guide-saudi` (هَب فرعي) · `mamaspapas-cot-mattress-bedding-saudi` · `mamaspapas-nursery-decor-themed-saudi`
- **ملابس الأطفال:** `mamaspapas-baby-clothing-guide-saudi` (هَب فرعي) · `mamaspapas-newborn-clothing-essentials-saudi` · `mamaspapas-baby-occasionwear-outerwear-saudi`
- **التغذية:** `mamaspapas-feeding-weaning-guide-saudi` (هَب فرعي) · `mamaspapas-highchair-booster-seat-saudi` · `mamaspapas-bibs-nursery-bags-saudi`
- **الاستحمام والهدايا:** `mamaspapas-bath-baby-care-saudi` (هَب فرعي) · `mamaspapas-gifts-hampers-newparents-saudi` · `mamaspapas-soft-toys-activity-gyms-saudi`

## الالتزام بسلامة `content_guardrails_playbook`

- **لا مقال مخصّص لمقاعد السيارة** (فئة سلامة حرجة). ذُكرت باحتراس في مقال العربات الرئيسي مع توصية بالتركيب مع فنّي معتمد.
- **لا مصدّات جانبية** في مقال المرتبة/الفراش. القسم بأكمله موجّه نحو "قواعد النوم الآمن" مع تحذير SIDS صريح.
- **الحليب والأغذية الرضيعة** مستثناة (YMYL) — مقال التغذية يركّز على الأدوات فقط.
- كل مقال ذي علاقة (استحمام، ألعاب، فراش، عربات، كرسي عالٍ) يحمل ملاحظة سلامة أعلى المقال.

## الربط الداخلي

- **الهَب الرئيسي** (`online-shopping-savings-guide-saudi-arabia`): سطر جديد لعنقود ماماز آند باباز في قسم «الأزياء والإطلالة».
- **`best-saudi-online-stores-2026`:** رابط ماماز موسّع للعنقود الكامل.
- **ربط شبكي متبادل مع ذا ديل + فوغا:** كل مقال ملابس/هدايا يشير لمقالات الأطفال في العنقودين الآخرين — سلطة تتحرّك عبر ثلاثة عناقيد.
- **متوسط الربط:** 9-13 رابطاً داخلياً/مقال.

## معلومات المتجر الحقيقية

- **name:** ماماز آند باباز (Mamas & Papas)
- **الخلفية:** براند بريطاني منذ 1981، عائلي متخصّص بالمواليد والأطفال
- **الكود:** `APP15` — 15٪ خصم على الطلب الأوّل من التطبيق
- **العرض الإضافي:** خصومات موسمية تصل 50٪
- **الأقسام (من الموقع مباشرة mamasandpapas.ae):** Strollers & Car Seats · Baby Clothes · Nursery · Feeding & Seating · Bath & Baby Care · Gifts & Toys · Brands (Cybex/Joie/Nuna/Maxi-Cosi/Stokke/Bugaboo)
- **الشحن:** السعودية والإمارات والكويت، 5-10 أيام عمل عادةً

## القرار التحريري: تجاوز قسم مقاعد السيارة

القسم كبير في المتجر (Infant/Toddler/All-in-One/Booster) لكنه فئة سلامة حرجة. الاختيار: **الالتزام بحرف guardrail** بدل تحقيق التغطية الكاملة. حلّ الوسط: **إشارة صادقة داخل مقال العربات الرئيسي** بأنّ ماماز يبيع مقاعد معتمدة (R129/ECE R44/04) مع توصية بمراجعة فنّي معتمد للتركيب — يحترم مصلحة الأمّ ولا يفتح ادعاءات سلامة.

## نمط الربط الشبكي بين العناقيد

الآن ثلاثة عناقيد أطفال متصلة (ذا ديل الفاخر / فوغا المتوسط / ماماز المتخصّص) — كل مقال يشير للمناسب في العنقودين الآخرين، ما يبني موقعاً كاملاً في نتائج تسوّق الأطفال السعودية بدل صفحة يتيمة لكل متجر.
