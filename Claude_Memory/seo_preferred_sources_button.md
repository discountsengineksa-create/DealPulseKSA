---
name: seo-preferred-sources-button
description: زر "أضِفنا كمصدر مفضّل" شُحن بالفوتر 2026-09-14 (web commit 7a185ea) + توضيح إعداد GSC "Search generative AI control" المنفصل عنه
metadata:
  type: project
  originSessionId: (verify facebook seo tips session)
  modified: 2026-09-14T19:50:15.968Z
---

**المصدر:** المالك لصق ٦ منشورات فيسبوك (Google Search Central) يطلب التحقّق منها. تحقّقتُ حيّاً بـWebFetch على وثائق جوجل الرسمية (developers.google.com + support.google.com) لا بالثقة بالمنشورات نفسها.

## ✅ تحقّق وشُحن — زر "المصادر المفضّلة" (Preferred Sources)

**الحقيقة مؤكَّدة:** ميزة حقيقية، انتشرت عالمياً لكل المواقع ٢٠٢٦-٠٨-٣١ (سابقاً محدودة). التطبيق الرسمي حرفياً سطران:
```html
<script async src="https://news.google.com/swg/js/v1/publisher.js"></script>
<div google-add-preferred-source-btn data-lang="ar"></div>
```
يمنح شارة "مفضّل" ورجحان ظهور في Top Stories/AI Overviews/AI Mode. **لا يؤثر على الترتيب مباشرة** (الوثيقة لا تدّعي ذلك). الأهلية العملية = نشر محتوى **طازج ومنتظم** على مستوى الدومين (لا مسار فرعي منفصل مؤهَّل باستقلالية) — نبض الصفقات مؤهَّل عملياً لأن محرّك [[seo-white-hat-only]] ينشر يومياً.

**شُحن:** web commit `7a185ea` (٢٠٢٦-٠٩-١٤) — السكربت في `app/layout.tsx` head، الزر في `components/Footer.tsx` (قسم "تابعنا")، مفتاحا ترجمة جديدان `footer_preferred_source` (ع/إ). تحقّق `npx tsc --noEmit` EXIT=0 قبل الدفع.

## ⚠️ ميزة منفصلة — Search Console "Search generative AI control" (يحتاج فعل المالك)

**ليست نفس الميزة أعلاه.** إعداد UI فقط (Settings → Search generative AI في GSC)، **بلا API** (تأكّد ٢٠٢٦-٠٨-١٢: `searchAnalytics` يرفض قيمة `generative-AI`) — لا يقدر أي Claude يفحصه أو يضبطه عن بُعد، لازم المالك يدخل GSC بنفسه.
- خياران: **Include** (افتراضي — المحتوى مؤهَّل يظهر كمصدر/رابط في AI Overviews + AI Mode + Discover التوليدي) أو **Exclude**.
- **صريح في الوثيقة: لا يؤثر على الترتيب ولا يشبه Google-Extended** (الأخير يتحكّم بالتدريب لا الظهور — نبض الصفقات مفعّل على ١٥-١٦ زاحف AI أصلاً في [[seo_ai_visibility_optin]]، قرار مختلف تماماً).
- **التوصية:** يبقى Include (الافتراضي) — يطابق استراتيجية opt-in القائمة في [[ai_citation_channel]] (القناة تضاعفت وتُنتج جلسات GA4 حقيقية). Exclude يعني التنازل عن نفس القناة التي أثبتت قيمتها.
- **فعل مطلوب من المالك (لا يقدر أي وكيل ينفّذه):** GSC → الإعدادات → Search generative AI → تأكّد أنه Include (على الأرجح كذلك افتراضياً وبلا فعل).

## ✔️ لا فعل مطلوب — مطابقان للمعمول به أصلاً
- **Scaled Content Abuse** (لقطة الشاشة الأولى): سياسة ٢٠٢٤ معروفة، موثّقة مسبقاً في [[seo_white_hat_only]] و[[content_guardrails_playbook]] بضوابط أشدّ من متطلّبات جوجل (كوبون فعّال + طول أدنى + سقف يومي + blocklist). لا تغيير في السياسة.
- **أفضل ممارسات meta description**: `app/layout.tsx` يضبط الوصف يدوياً ضمن ١١٠-١٥٨ حرفاً أصلاً (تعليق بالكود يوثّق الحدّ) — مطابق للوثيقة الرسمية بلا حاجة تعديل.
- **الروابط الداخلية**: مطابق لِـ[[blog_internal_link_deorphan]] و[[content_guardrails_playbook]] (٩-١٣ رابط داخلي لكل مقال) — لا فجوة.

يخدم: [[seo_ai_visibility_optin]] · [[ai_citation_channel]] · [[website_seo_engine]]
