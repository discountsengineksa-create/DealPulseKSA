---
name: domain-authority-plan
description: خطة بناء سلطة الدومين لـ DealPulse (White-Hat) + تقدّم الربط الداخلي
metadata: 
  node_type: memory
  type: project
  originSessionId: c8ccad06-7d83-44c1-818c-fa4fb4403204
---

خطة رفع سلطة دومين dealpulseksa.com (موقع جديد، سلطة ضعيفة). رافعتان: **روابط خلفية** (الأقوى لكن جهد خارجي + شهور) و**سلطة موضوعية** (محتوى + ربط داخلي + تقني + E-E-A-T — بيدنا وأسرع). قيد إلزامي: White-Hat فقط (لا شراء روابط/PBN/سبام) — انظر [[seo-white-hat-only]]. التوقّع: شهور، لا قفزات.

**✅ منجز — الربط الداخلي (2026-06-20، web commit b7bebe6):** كانت صفحات `/c/` **يتيمة** (sitemap فقط). الحل (server-rendered HTML):
- `app/store/[slug]/page.tsx`: صفحة المتجر تعرض «📖 أدلة كود خصم {متجر}» تربط لصفحات `/c/` الخاصة به (مطابقة `seoPage.master_id === store.id`، lang=ar) → يُخرجها من اليُتم ويمرّر سلطة.
- `app/c/[slug]/page.tsx`: «أدلة ذات صلة» (نفس اللغة، 6 روابط) → يشبك صفحات الهبوط ببعض.

**المتبقّي (اختيار المالك بدأ بالربط الداخلي):**
- **عناقيد محتوى** (topical authority): توسعة المدوّنة `lib/blog.ts` — عنقود المكمّلات منجز [[health-content-cluster]]؛ **بدأ العنقود المحلي**: مقال «دليل العود والعطور» منشور (2026-06-20، web b96d8b7، slug `oud-perfume-guide-saudi-arabia`، category «عطور وعود»، مربوط داخلياً بمتاجر حقيقية عود رويال/قولدن فلورا/فيرست لايف/فوغا كلوسيت + تصنيفي عطور وعود + /c/ golden-flora). التالي: تمور/عبايات/إلكترونيات [[salla-affiliate-channel]]. ⚠️ **بوتيرة معتدلة (1-2/أسبوع) — تجنّب Scaled Content Abuse** (الخط الأحمر في [[seo-white-hat-only]]).
- **بيانات منظّمة (Schema)**: Organization + Breadcrumb + Article + FAQ (بعضها موجود في lib/seo/schema.ts — مراجعة/توسعة).
- **روابط خلفية (جهد المالك)**: أدلة أعمال سعودية، أدلة كوبونات، بروفايلات سوشيال موثّقة، قوائم شركاء Salla/Admitad.
- **تسريع الفهرسة** (مكمّل): GSC → إعادة إرسال sitemap + «طلب الفهرسة» لصفحات /c/ المهمة؛ IndexNow يغطّي Bing/Yandex/Naver/Seznam (Google لا).
