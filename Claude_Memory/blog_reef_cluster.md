---
name: blog_reef_cluster
description: عنقود ريف (بيت عطور سعودي + ريف بيوتي للشفاه) 18 مقالاً — master.id=90 كود B71 خصم 5%؛ عطور مرقّمة/مسمّاة + فوّاحات منزل + مكياج شفاه؛ استُرجع من جلسة سابقة غير مدفوعة
metadata:
  node_type: memory
  type: project
---

**٢٠٢٦-٠٩-١٠** — عنقود ريف كان **جاهزاً في `lib/blog.ts` بلا commit** من جلسة سابقة (مخالفة الحائط ٧). فُحص نصّياً ودُفع (`af7db8c`) بعد إذن المالك «ادفع».

## المتجر — ريف (Reef)

- `master.id=90` · `store_id='ريف'` · `name_en='Reef'` · `public_coupon='B71'` · **خصم 5%** (`discount_value='5%'`) · `my_coupon='5%'` (نسبة العمولة — عُرف بوستيني، صدفةً تساوي الخصم؛ حقل داشبورد فقط، ليس بايتاً) · `affiliate_link=reefperfumes.com` · `store_tags={عطور, معطرات جو, شعر, هدايا}` · `source_platform='بوستيني'` · `cloaked_slug='be36d4cfe1'` · `seo_enabled=true`.
- **`store_bio` مكتوب مسبقاً** (علامة عطور سعودية، عود نادر + زهور + توابل؛ عطور + جسم/شعر + ريف بيوتي + عطور منزل + بطاقات إهداء؛ شحن مجاني فوق 299 ريال، توصيل 3 ساعات). `extra_offer='شحن مجاني للطلبات فوق 299 ريال'`.
- `/store/ريف` → 200 («كود خصم ريف»). كان مربوطاً من صفر مقال.
- التحقّق من الكتالوج: `reefperfumes.com` (بوستيcrib) — العنقود بُني قبل هذه الجلسة، لم يُعَد فحص الكتالوج الحيّ.

## الـ18 مقالاً (`af7db8c` — بادئة `reef-`، `category: 'عطور وعود'` → alias `oud`)

pillar `reef-guide-saudi` · `reef-perfumes-guide-saudi` · `reef-numbered-perfumes-guide-saudi` · `reef-pure-collection-guide-saudi` · `reef-arab-oud-perfumes-guide-saudi` · `reef-womens-perfumes-guide-saudi` · `reef-mens-perfumes-guide-saudi` · `reef-body-hair-perfumes-guide-saudi` · `reef-home-fragrance-diffuser-guide-saudi` · `reef-diffuser-oil-refill-guide-saudi` · `reef-beauty-lipstick-rosella-guide-saudi` · `reef-beauty-lip-liner-gloss-tint-guide-saudi` · `reef-perfume-longevity-projection-guide-saudi` · `reef-choose-perfume-by-occasion-scent-family-saudi` · `reef-3-for-1-offers-guide-saudi` · `reef-national-day-ramadan-sets-guide-saudi` · `reef-gift-cards-guide-saudi` · `reef-coupon-b71-how-to-use-saudi`.

de-orphan: بنود ريف مُدرجة داخل ~9 هَبّات عطور/عود قائمة (`perfume-brands-*`, `fragrance-families-*`, أدلّة بلوار/رسيس/الماجد/الدخيل/بيوتي سيكرتس).

## التحقّق (محدود — الجهاز يـOOM على `next build`)

`esbuild --bundle lib/blog.ts` **EXIT=0** · 1908 مقالاً إجمالاً · 18 ريف بلا حقول ناقصة · صفر slug مكرّر · صفر رابط `/blog/` مكسور · صفر كتلة سؤال/جواب ملتصقة (`extractFaq`). **البناء الكامل لم يُشغَّل — فيرسيل هو البناء المرجعي.**

## معلّق

- **`blog_bridge`** — لم يُعَد بناؤه (كتابة DB). ريف + 18 مقالاً غير مربوطين في البحث الذكي بعد.
- لا ملف ذاكرة كان موجوداً قبل هذه الجلسة — أُنشئ الآن.

يكمّل [[blog_beluar_cluster]] · [[blog_rasees_cluster]] · [[blog_beautysecrets_cluster]] · [[content_guardrails_playbook]] · [[voice_bible]] · [[feedback_always_push]].
