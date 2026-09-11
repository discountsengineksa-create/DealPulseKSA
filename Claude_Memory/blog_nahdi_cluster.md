---
name: blog_nahdi_cluster
description: عنقود صيدلية النهدي أونلاين 20 مقالاً — master.id=91 كود 9LDF خصم 5% (حد 25 ريال، عملاء جدد، يستثني الأدوية وحليب الأطفال)؛ منضبط YMYL (لا فورمولا رضّع، لا مكمّلات حمل/أمراض مزمنة، لا مقاعد سيارة)
metadata:
  node_type: memory
  type: project
---

**٢٠٢٦-٠٩-١٠** — المالك أرسل ~١١ لقطة من nahdionline.com (شجرة الفئات) وقال «ابدء في سيو النهدي». نُفّذ بعد الطبقة ٠ ([[content_guardrails_playbook]] · [[feedback_verify_catalog_before_claim]] · [[voice_bible]] · [[protocol_partnership]] · [[seo_white_hat_only]] · [[blog_beautysecrets_cluster]] · [[blog_reef_cluster]]).

## المتجر — صيدلية النهدي (Nahdi)

- `master.id=91` · `store_id='صيدلية النهدي'` · `name_en='Nahdi'` · `public_coupon='9LDF'` · **خصم 5%** (`discount_value='5%'`) · `affiliate_link=https://www.nahdionline.com` · `source_platform='بوستيني'` · `cloaked_slug='26ff1e7582'` · `seo_enabled=true` · `store_bio` مكتوب.
- `store_tags={مستلزمات طبية, جمال وعناية شخصية, صحة وعافية, بشرة, شعر, الكترونيات, أطفال, مكياج}`.
- `extra_offer='عملاء جدد · توصيل منزلي · حد أقصى 25 ريال · يستثني الأدوية وحليب الأطفال'` — **قيد العرض مثبّت في المتن كله**.
- `my_coupon='6%'` = **نسبة العمولة، صحيحة** — نفس عُرف المالك لكل متاجر بوستيني (الدخيل/دبدوب/FNP/مودانيسا/نايس كلها `my_coupon` = نسبة). الحقل داشبورد فقط، لا يقرأه البوت/API/الموقع. ❌ ادّعاء «غلط» سابق هنا كان خطأً (درس ناتشورال تاتش يخصّ متاجر التتبّع المباشر لا بوستيني).
- `/store/صيدلية النهدي` → 200 (بعد 308 apex→www). كان مربوطاً من صفر مقال.
- التحقّق من الكتالوج: لقطات المالك لشجرة فئات nahdionline.com (عطور/مكياج/بشرة/شعر/عناية شخصية/فيتامينات/تغذية رياضية+صحية/أجهزة طبية/رعاية منزلية/مستلزمات أم وطفل/إلكترونيات).

## انضباط YMYL (الحائط الحاسم في هذا العنقود)

صيدلية = خطر YMYL عالٍ. **استُثني صراحةً في المتن، مع ذكر السبب:**
- **حليب/طعام الرُّضّع** — قرار طبيب الأطفال (والكود نفسه يستثنيه).
- **مكمّلات الحمل + إدارة الأمراض المزمنة (قلب/سكري/نوم) + التحكم بالوزن + فيتامينات الأطفال** — بوصفة/مشورة، لا من مقال. مقال الفيتامينات يذكر هذا الاستثناء نصّاً.
- **مقاعد سيارة الأطفال + مصدّات/وسائد السرير** — سلامة حرجة.
- **قسم «الصحة الجنسية»** في عناية النهدي — لم يُكتب عنه إطلاقاً (حائط المحتوى الجنسي).
- الأدوية OTC — خارج النطاق (الكود يستثنيها والزاوية تجارية غير دوائية).
كل مقال بشرة/شعر/فيتامينات/أجهزة يحمل إخلاء «تجميلي/تثقيفي لا نصيحة طبية» + «استشر الصيدلي/الطبيب».

## الـ20 مقالاً (`c3934c7` — بادئة `nahdi-`، دفعة واحدة)

pillar `nahdi-guide-saudi` (فئة `صحة وعافية`).
عطور: `nahdi-perfumes-guide-saudi` · `nahdi-womens-perfumes-guide-saudi` · `nahdi-mens-perfumes-guide-saudi` (فئة `عطور`→beauty).
جمال: `nahdi-makeup-guide-saudi` (`جمال ومكياج`) · `nahdi-skincare-guide-saudi` · `nahdi-sunscreen-guide-saudi` · `nahdi-korean-beauty-guide-saudi` · `nahdi-hair-care-guide-saudi` · `nahdi-personal-care-guide-saudi` (فئة `جمال وعطور`→beauty).
صحة: `nahdi-oral-care-guide-saudi` · `nahdi-vitamins-guide-saudi` · `nahdi-hair-skin-vitamins-guide-saudi` · `nahdi-sports-nutrition-guide-saudi` (`رياضة`→sports) · `nahdi-healthy-nutrition-guide-saudi` · `nahdi-medical-devices-guide-saudi` (فئة `صحة وعافية`→health).
أطفال: `nahdi-baby-mother-essentials-guide-saudi` (`أطفال`→kids).
عمليات: `nahdi-coupon-9ldf-how-to-use-saudi` (`أدلّة التوفير`) · `nahdi-app-delivery-guide-saudi` (`أدلّة التوفير`) · `nahdi-national-day-ramadan-offers-guide-saudi` (`هدايا`→gifts).

لا فئة `BLOG_CATEGORIES` جديدة — الكل يخرّط على beauty/health/sports/kids/gifts/savings-guides موجودة.

## قرارات مثبّتة

- **صفر فبركة:** لا رقم ريال (مستويات وصفية اقتصادي/متوسط/متقدّم)؛ لا ادّعاء «أصلي/معتمد» بلا دليل؛ فضح أكواد «50-70%» الوهمية؛ حدّ الكود 25 ريالاً محسوب صراحةً (يتحقّق عند سلّة ~500 ريال).
- **الكود يخدم الجمال/العناية/الفيتامينات/الأجهزة لا الدواء** — رُتّبت التوصية على هذا.
- **de-orphan (5 هَبّات، سطر واحد لكلٍّ):** `best-saudi-online-stores-2026` · `makeup-guide-beginners-saudi-arabia` · `beauty-skincare-guide-saudi-arabia` · `multivitamin-guide-saudi-arabia` · `vitamin-d-guide-saudi-arabia`. (تجنّب `perfume-brands-saudi-arabia` — جدول «دُور عطور» والنهدي صيدلية لا دار.)

## التحقّق (محدود — الجهاز يـOOM على `next build`)

`esbuild --bundle lib/blog.ts` **EXIT=0** · 1928 مقالاً · 20 nahdi بلا حقول ناقصة · صفر slug مكرّر · صفر رابط `/blog/` مكسور · صفر كتلة سؤال/جواب ملتصقة · صفر ``` أو `${` في المتون · روابط داخلية 5–25/مقال (العملياتية 5–6). **البناء الكامل لم يُشغَّل — فيرسيل هو المرجع.** ⚠️ غلطة تأليف أوّلية: كتبتُ `\` قبل باكتيك الإغلاق في الـ20 متناً (باكتيك مهرَّب = السلسلة لا تُغلق) — أُصلح بسكربت قبل الدفع؛ **القاعدة: باكتيك الإغلاق سطرٌ من حرفين `` `, `` بلا backslash**.

## معلّق

- **`blog_bridge`** — تمّ فعلياً (بعد إصلاح خلل ترميز في السكربت نفسه — [[feedback_harness_blocks_self_permission]]). العدّ الحيّ النهائي: **١٧٢٤ صفّاً / ٧٦ متجراً**، النهدي ٢٠ مؤكّدة.

## الصراحة الاستراتيجية (قيلت للمالك)

سقف العائد = سلطة الدومين لا المحتوى ([[seo_page_portfolio_verdict]] · [[content_guardrails_playbook]] §🎯). لكن «كوبون النهدي» طلب براند حقيقي كبير، والعنقود مبرَّر على البراند + قناة استشهاد AI ([[ai_citation_channel]]) لا التكديس.

يكمّل [[blog_reef_cluster]] · [[blog_beautysecrets_cluster]] · [[voice_bible]] (عيّنة فيتامين د YMYL).
