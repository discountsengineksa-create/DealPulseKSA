---
name: seo_authority_building
description: تشخيص crawled-not-indexed = سقف سلطة لا باغ؛ المسار المختار بناء باكلينكس White-Hat (قنوات مملوكة، لا Reddit/Quora/مدوّنين)
metadata: 
  node_type: memory
  type: project
  originSessionId: aec8e522-6145-4f43-9107-54224967fe06
---

**التشخيص (2026-07-14):** Search Console للموقع: 893 مفهرسة / 306 غير مفهرسة. تقسيم الأسباب: **241 «تم الزحف — لم تُفهرَس» + 61 «تم الاكتشاف — لم تُفهرَس» = 302** (حكم قوقل على القيمة/السلطة، **لا باغ تقني**)؛ التقني 4 صفحات فقط (404×1 + canonical×3). نقرة «التحقق» على crawled-not-indexed **فشلت (239)** — لأنها لا تُحلّ بزر. أمثلة الـ241 كلها **دفعات المقالات المولّدة بالجملة** (topbeauty/oudroyal/banara/eleghub/karkstream/wolvex/hadaf/noon/huawei...) = عناقيد الـ[[blog_14clusters_july11]] و[[blog_7clusters_july11]]. السبب: نطاق شاب بباكلينكس شبه صفر ← «ميزانية فهرسة» محدودة + تشابه/رقّة على نطاق كبير (تحقّق تحذير «لا 1000 صفحة رقيقة» في [[content_programmatic_strategy]]).

**الدرس:** توليد صفحات أكثر يزيد الطين بلّة؛ إعادة ضخّ Indexing API لا تُجبر فهرسة صفحة ضعيفة. الرافعة الوحيدة = **السلطة**.

**التقدّم:**
- ✅ **Find Saudi** (findsaudi.com) — أُدرج نبض الصفقات (2026-07-14) تحت **«اتصالات و إنترنت › تسوّق، تجارة الكترونية»** (لا «دعاية وإعلان» — تلك للوكالات). حالة: «تم بنجاح»، بانتظار مراجعة ~24 ساعة. قيمة متواضعة (إشارة كِيان لا رافعة ترتيب). التالي المعلّق: Bedinroom partner email + Google Business Profile.
- ⚠️ **تعارض بريد لم يُحسَم:** موقع الويب `lib/seo/constants.ts` ينشر `dealpulseksa@gmail.com` (pulse)، بينما [[contact_emails]] يسجّل `dealpulesksa@gmail.com` (pules). واحد خطأ ويُنشَر لقوقل — اسأل المالك أيّهما الصندوق الفعلي قبل تثبيته.
- الحسابات الرسمية (من constants.ts، sameAs): IG/X/FB = `dealpulseksa`، بوت تيليجرام `t.me/DealPulseksa_bot`، Threads `@dealpulseksa`.

**القرار (المالك اختار):** **بناء السلطة**. الخطة الكاملة في ريبو الويب `seo/authority_building_plan.md` (web commit `a62c6fb`). White-Hat فقط، وقناعة القنوات المملوكة من [[seo_owned_channels_pivot]] (لا Reddit/Quora/مدوّنين). طبقات: (1) استشهادات أساسية GBP/Trustpilot/LinkedIn/Crunchbase/أدلّة سعودية (Saudi Bizness/Find Saudi/KSA Directory) (2) روابط سياقية وثيقة الصلة — **الأولوية: إيميل طلب رابط شراكة من Bedinroom** (أفلييت جديد + بنينا لهم هَب [[blog_bedinroom_cluster]]) + دليل شركاء هيئة السياحة partner.visitsaudi.com + ملفات ناشر Admitad/Salla (3) أصل قابل للربط /calendar (4) PR اختياري. بطاقة NAP موحّدة + إيميل Bedinroom جاهزان في الملف. Trustpilot أول باكلينك مكتمل ([[domain_canonical_trap]]).
