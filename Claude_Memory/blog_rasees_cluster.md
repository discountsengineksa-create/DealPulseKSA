---
name: blog_rasees_cluster
description: عنقود رسيس (بيت عطور سعودي بعلامة واحدة) 16 مقالاً — master.id=87 كود RA50 7%؛ توقيعه مجموعة نيش بأسماء معالم السعودية؛ صفر فبركة (المالك حذّر: يسوّي إعلانات كثيرة، لا تتحمّس)
metadata:
  node_type: memory
  type: project
  originSessionId: 3b177687-1150-4a44-96a1-4e703647f3fa
---

**٢٠٢٦-٠٩-١٠** — المالك أرسل ~١٤ لقطة من rasees.net وطلب «ابدأ في رسيس، اهتم فيه لأنه دايم يسوّي إعلانات، لكن لا تتحمّس ولا تفبرك شي؛ سيو وصفحات شاملة + روابط داخلية مع متاجرنا اللي لها نفس الاهتمامات».

## المتجر — رسيس (Rasees)

- `master.id=87` · `store_id='رسيس'` · `name_en='Rasees'` · كود **RA50** · خصم **7%** · `store_tags={عود و بخور, عطور, هدايا}` · `affiliate_link=rasees.net` · **`bio` فارغ** (يحتاج كتابة — DB، لم يُكتب).
- `/store/%D8%B1%D8%B3%D9%8A%D8%B3` → **200** (عنوان «كود خصم رسيس 7% فعّال 2026»). **كان مربوطاً من صفر مقال.**
- **ملاحظة API:** `seo_enabled` يرجع `None` لكل المتاجر في `view=full` (المطار/دبدوب/نايس أيضاً) — **ليس إشارة استبعاد**؛ صفحة `/store` الحيّة 200 هي الدليل.

## الحقائق المؤكّدة (WebFetch rasees.net/ar + لقطات المالك)

- **بيت عطور سعودي بعلامة واحدة** — ليس متجراً يجمع ماركات. شعار: «نهتم بكل التفاصيل لنقدم لك عطراً يليق بك».
- الأقسام: عطور (رجالي/نسائي/للجنسين) · **عطور نيش** · عطور شعر · زيوت عطرية · عود وبخور · مسك · معطرات هواء · أجهزة تعطير (متنقّل/ذكي) · أطقم هدايا · **باقات مهرجان رسيس** · له **فروع**.
- الدفع: **تابي + تمارا + إمكان** (من لقطات صفحات المنتج).
- **مجموعة النيش = التوقيع:** أسماء معالم/مشاريع سعودية بهرم روائح لكلٍّ (كلها من لقطات المالك، فئة النيش): نيوم · العلا · الدرعية · الطريف · ذا لاين · القدية · طويق · الرياض.
- **لم يعلن الموقع:** منشأ العود، نقاء طبيعي، جوائز، «صُنع في». → **فلا يُدّعى أيٌّ منها** ([[feedback_verify_catalog_before_claim]]).
- ⚠️ مواقع كوبونات تنشر أكواداً وهمية لرسيس (R100/AA35/LI15/AA70 بنسب 50–70٪). **المعتمد RA50 = 7٪** فقط — مقال الكوبون يفضح هذا صراحة.

## الـ16 مقالاً (`8276493` — دفعة واحدة، بادئة `rasees-`)

pillar `rasees-guide-saudi` · `rasees-niche-collection-saudi-landmarks-guide` (التوقيع، جدول الأهرام الـ8) · `rasees-best-selling-perfumes-guide-saudi` (ستار/فالي/روزس/انتنس/بلاك/برايفت/سولو/ادور) · `rasees-mens-perfumes-guide-saudi` · `rasees-womens-perfumes-guide-saudi` · `rasees-hair-perfume-mist-guide-saudi` (إخلاء + كحول/شعر) · `rasees-fragrance-oils-guide-saudi` · `rasees-oud-bakhoor-guide-saudi` (صدق التوصيف: «فاخر/سوبر» تصنيف المتجر لا الشجرة) · `rasees-musk-guide-saudi` · `rasees-home-fragrance-diffusers-guide-saudi` · `rasees-gift-sets-guide-saudi` · `rasees-festival-bundles-offers-guide-saudi` (تأطير بارد: «العروض تتكرّر، لا تشترِ باقة لا تحتاجها») · `rasees-coupon-ra50-how-to-use-saudi` · `rasees-installments-tabby-tamara-emkan-saudi` · `rasees-perfume-longevity-projection-guide-saudi` · `rasees-choose-perfume-by-occasion-scent-family-saudi`.

فئة: `category: 'عود وبخور'` (نفس عناقيد الدخيل/الماجد/القرشي → alias `oud`).

## قرارات مثبّتة

- **صفر فبركة (طلب المالك الصريح):** مستويات وصفية لا أرقام ريال (`grep` ريال = 0 لكل مقال)؛ أهرام النيش من اللقطات لا من الخيال؛ لا ادّعاء منشأ/نقاء/جوائز؛ العود = «منتج تبخير منزلي جيّد لا دهن استثماري».
- **الربط الداخلي مع متاجر نفس الاهتمام:** أدلّة العطور/العود الموجودة (`perfume-buying-guide`, `fragrance-families-guide`, `perfume-notes-pyramid`, `oud-types-guide`, `real-vs-fake-oud`, `oud-prices-guide`, `oud-burning-guide`, `oud-oil-application`) + صفحات `/store` للأقران (عود رويال، بنت الشيخ، في للعطور) + أدلّة الأقران (asq-guide، almajed-guide، aldakheel-guide، goldenflora-*).
- **de-orphan:** أُضيف بند رسيس في **8 مقالات هَب** `perfume-brands-*` (المطابقة الموضوعية تامّة، ليست «توسيع نطاق») + في `oud-bukhoor-guide-saudi-arabia`.
- **البوت/الإعلانات:** رسيس نشط تسويقيّاً جداً (مهرجان رسيس، باقات بيت العمر/فلة، هدية-مع-الطلب، صور سيارات) — عولج **كسياق تسويقي لا حقيقة**: «تفاصيل الباقة تحدّدها صفحة العرض وقت شرائك».

## التحقّق

`next build` كامل **EXIT=0** · 2237/2237 صفحة · 16 صفحة تُصيَّر بـ`FAQPage` + RA50 · صفر ``` ثلاثية · صفر `${` · صفر رابط مكسور · صفر slug مكرّر · صفر خلط عربي/لاتيني. الإجمالي **1839 → 1855**.

## معلّق

- **`bio` المتجر فارغ** — كتابته DB، لم تُنفَّذ. جاهز للمالك.
- **`blog_bridge`** — لم يُعَد بناؤه (كتابة DB). رسيس + 16 مقالاً غير مربوطين في البحث الذكي بعد.

يكمّل [[blog_almajed_cluster]] · [[blog_aldakheel_cluster]] · [[blog_asq_cluster]] · [[content_guardrails_playbook]] · [[voice_bible]] · [[feedback_verify_catalog_before_claim]].
