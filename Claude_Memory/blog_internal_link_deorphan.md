---
name: blog-internal-link-deorphan
description: تدقيق الربط الداخلي لمدوّنة الويب (649 مقال) — 65 مقال يتيم صُفِّرت عبر إكمال فهارس الـpillars؛ الطريقة + سكربتات قابلة لإعادة الاستخدام
metadata: 
  node_type: memory
  type: project
  originSessionId: 8f539881-da98-4e78-aa1a-629208bf7e77
---

مدوّنة الويب (lib/blog.ts، 649 مقال) كان فيها **65 مقال يتيم فعلياً** (2026-07-07، web commit 98b4329): صفر رابط داخلي سياقي داخل إليها — لا من متن مقال آخر ولا من widget «مقالات ذات صلة». هذه هي جوهر الـ**244 «مكتشفة لم تُفهرس»** في GSC (انظر [[seo-indexation-status]]).

**السبب الجذري:** `getRelatedPosts` في lib/blog.ts يُبقي أعلى 6 فقط بالسكور (تطابق أول token +15، ثاني +10، تصنيف +5، تداخل كلمات +6، hub-pin +25). في عنقود فيه 30-70 مقال، الـtop-6 يتشبّع بأقرب الإخوة فيسقط ذيل العنقود من قائمة كل صفحة → يُتم. **زيادة المحتوى تُفاقم هذا** (مبرّر آخر لتوصيتي المتكرّرة: الباكلينك والربط الداخلي أهم من عدد الصفحات).

**الحل (يطابق نمط المالك المعتمد «de-orphan via hub» في كوميتاته):** ربط كل يتيم من hub قوي — لا تغيير الخوارزمية (مخاطرة على كل الصفحات):
- أكملتُ فهرس الأبناء داخل قسم «## استكشف» في 4 pillars: `tools-home-buying-guide` (53) · `kids-toys-buying-guide` (71) · `phone-accessories-buying-guide` (54) · `home-furniture-buying-guide` (51) — بلوك «### الفهرس الكامل». هذا هندسة hub→spoke سليمة (50-70 رابطاً موضوعياً متجانساً على صفحة hub ليس spam).
- 10 أدلة قطع سيارات → pillar `aliexpress-cars-guide`.
- المكمّلات (creatine/multivitamin/whey كانت يتيمة تماماً — أدلة المكمّلات بلا أي رابط /blog متبادل) → بلوك «## أدلّة المكمّلات ذات الصلة» في vitamin-d/magnesium/probiotics يربط الستة.
- 5 نماذج معلمين يتيمة → hub `teacher-records-templates-guide-saudi`.
- 3 مفردات (noon-vs-namshi، womens-leggings، kids-sleepwear) → hubs مناسبة.

**النتيجة:** يتامى 65→**0**. +262 رابط داخلي سياقي، إضافات فقط. esbuild نظيف.

**طريقة التدقيق (قابلة للتكرار — السكربتات في scratchpad):** حاكِ خوارزمية `getRelatedPosts` + relatedKeywords + RELATED_STOP_WORDS بـNode، احسب inbound الديناميكي (كم مرة يظهر المقال في top-6 لغيره) + inbound المتني (regex `\]\(\/blog\/slug\)`)؛ يتيم = مجموعهما صفر. **⚠️ الـ/blog index يسرد كل المقالات (getAllPosts) فيُلغي «اليُتم» بمعنى Ahrefs الصارم، لكن اليُتم في الغراف السياقي = ضعف تمرير سلطة + دفن في ميزانية الزحف.** تحقّق دائماً: أعِد تشغيل الغراف + `esbuild lib/blog.ts --bundle` (البناء المحلي الكامل OOM، لكن esbuild سريع وخفيف) + تكافؤ الـbacktick.

**المتبقّي (طبقة weak):** ~110 مقال بـinbound=1؛ مقبول (رابط واحد من pillar قوي كافٍ للاكتشاف)، لكن يمكن تعميق لاحقاً. **العنق الأكبر يبقى الباكلينك** [[domain-authority-plan]] لا الربط الداخلي. يكمّل [[seo-indexation-status]] و [[blog-aliexpress-cluster]].
