---
name: Maqalat AdSense Readiness Sweep
description: 2026-09-12 — التطبيق العملي لدروس DealPulse SEO/content على maqalat.org لتقصير مسار الموافقة على AdSense. صفحات ثقة مُقوّاة + de-orphan آلي + سكربتات مسح قابلة لإعادة التشغيل.
type: project
originSessionId: ba0ddc64-d7f5-4764-afa1-cce83b257794
---
## السياق

المالك طلب صراحةً (٢٠٢٦-٠٩-١٢): «استفيد من قدرات وعقل كلود الجهاز الأوّل في كل شيء بشرط
ما تأخذ أي شيء يخص مشروع نبض الصفقات… كل شي ينفع للغاية النهائية Google AdSense». أي نقل
**الأنماط** لا **الأعمال** — voice، guardrails، de-orphan tech، trust-page rigor.

## ما أُنجز (commit `60dc38d`)

**سكربتات المسح (قابلة لإعادة التشغيل):**
- `scripts/audits/adsense_readiness_scan.mjs` — offline scanner يفحص ٢٥٨ مقالاً على:
  passive-ratio، AI-tell openings/enders، human-signal density، missing-table، thin content،
  orphan pages، uncited YMYL numbers. يكتب JSON كامل في `adsense_readiness_report.json`.
- `scripts/audits/deorphan_low_link_articles.mjs` — يقرأ التقرير ويحقن قسم «مواضيع ذات
  صلة» في المقالات ذات <٣ روابط داخلية inline. Idempotent عبر علامة `{/* deorphan-auto */}`.

**نتائج المسح (٢٥٨ مقالاً، عربي+إنجليزي):**
- متوسط الروابط الداخلية inline: **٨.٦٤/مقال** (قريب من هدف DealPulse ٩-١٣) ✅
- ٢٢٥/٢٥٨ مقال ≥٦ روابط (٨٧٪) ✅
- **٤ مقالات بصفر رابط** + **١٦ بأقل من ٣** = ٢٠ فُعِل عليها de-orphan (+٤ لكل = ٨٠ رابطاً جديداً)
- **١٠٠ مقال بلا جدول** — لم يُعالَج (يدوي)
- **٢٧ مقالاً <٧٠٠ كلمة** — لم يُعالَج (يدوي)
- **٢١ مقال YMYL بأرقام inline غير موثّقة** — رُصد، لم يُعالَج (يدوي بأولوية عالية)
- **٠ مقال «نظيف»** (بلا أعلام) لأن مقياس human-signals عربي فقط فكل EN جاء human-0 خطأً — bug في الماسح لم يُصلَح بعد.

**تقوية صفحات الثقة:**
- `editorial-policy`: حُذفت Mayo Clinic من قائمة المصادر الطبية (تحجب الروبوتات، يفحصها Ahrefs
  ككسر — راجع [[health_citation_sourcing]]). أُبدلت بـHarvard Nutrition Source + WHO + NIH
  + CDC + ACOG + Cochrane. رُبطت `/author/founder` من قسم الشفافية. أُضيف mailto إلى قسم
  التصحيحات (كلا اللغتين).
- `about`: `whoBody` صار يربط `/author/founder` عبر `rel=author` (شكل rich-text عبر `<team>`
  tag في ملفات الرسائل).
- `pregnancy-calculator-guide.mdx`: نفس استبدال Mayo → ACOG + NICE.

## دروس نُقلَت من نبض الصفقات (بلا نقل أعمال)

- **صيغة قياس الجودة، لا القاعدة النظرية**: playbook §٦ («فريق مقالات» يقتل E-E-A-T) طُبِّق
  كـ**بنية** (سجل كتّاب، صفحة /author/founder، Person/Organization schema، ربط من الصفحات
  الثقة) لا كنقل محتوى.
- **De-orphan رياضي لا يدوي**: خوارزمية stride-sampling موجودة أصلاً في
  `lib/blog.ts::getRelatedArticles` — سلمت المقالات من «top-6 يُجوّع الذيل». المشكلة كانت
  فقط في inline body links (المتن)، لا في related-articles system.
- **مصادر ميتة عند الكراولر = ديْن**: Mayo Clinic أفرز نصائح عن «صحة الأسرة» بديلة (Harvard/
  WHO/NIH). القاعدة الجديدة: **قبل ذكر أي مصدر طبي في صفحات الثقة، فُحص هل يسمح للـcrawlers
  أم يعطي 403**.

## توسيع المحتوى (٢٠٢٦-٠٩-١٢، دفعة ثانية، commits `82f3901` + `e1e345c` + `436560e`)

المالك أكّد شرط الكتابة: **معلومات حقيقية + مصادر رسمية + صفر حشو + ٨٠٠-١٦٠٠ كلمة + صفر
فبركة**. الصفحات ذات الطابع الأداتي (حاسبات/تقاويم/عدّادات) مستثناة من حدّ ٨٠٠. تحت هذا
العقد الكتابي، وُسّع **١٨ مقالاً** بمعلومات جديدة موثّقة (لا حشو). كل توسّع يضيف قسماً أو
قسمَين بمعدّل ١٥٠-٣٥٠ كلمة، كل ادّعاء بمصدر رسمي inline:

**عنقود AI (١٢ مقالاً)**: common-prompt-mistakes (Chain-of-Thought بمرجع Wei et al. + Anthropic
XML tags + مثال متكامل عقد عمل)، context-window-explained (رياضيات التسعير الحقيقية لـAPI +
تجزئة العربية الخاصّة)، chatgpt-best-work-uses (SDAIA PDPL Compliance)، effective-prompt-writing-rules
(كسر القواعد + تقنية القوالب بمتغيّرات)، gpt-4-vs-gpt-5-vs-o3 (شجرة قرار + جدول latency
للإنتاج)، gemini-vs-chatgpt-detailed (فارق الأداء العربي + مصفوفة الحسّاسية للبيانات)،
arabic-vs-english-prompting (رياضيات فجوة بيانات التدريب + مسار ٣ خطوات للمحتوى العربي
الرفيع)، chatgpt-weaknesses (الاختبار الذاتي MIT + Mata v. Avianca مفصَّلاً)، chatgpt-advanced-voice-and-sora
(قانون السعودية لتوليد الفيديو + ميزانية Sora الحقيقية)، chatgpt-for-students (كاشفات
الغشّ + جدول استخدام لكل مادّة)، gemini-live-and-veo (interruption handling + مقارنة Veo 2 vs 3)،
temperature-top-p-explained (رياضيات softmax + seed=42 للاختبار)، gemini-in-google-workspace
(Workspace DPA + ٥ ميزات مُغفلة).

**عنقود Government (٥ مقالات)**: tawakkalna (النسخة الموسّعة + الفرق بين تسميتَيه)،
traffic-violations (المخالفات المرصودة آلياً + متى الاعتراض ينجح)، absher (تمييز الأنواع
الثلاثة + مصفوفة قرار مع توكلنا)، saudi-id-renewal (مدد الصلاحية بحسب العمر + تحديث رقم
التسلسل)، runway-ml-signup-and-usage (حقوق تجارية بحسب الاشتراك + رياضيات credits).

**سكربت اختبار مضاف**: `scripts/audits/internal_link_check.mjs` — ٠ روابط داخلية مكسورة.
**JSON-LD أُضيف لكل صفحات الثقة** (`staticPageJsonLd`): AboutPage/ContactPage/WebPage.

## المتبقّي لـAdSense بعد دفعة اليوم

- **٤٢ مقالاً لا يزال تحت ٨٠٠ كلمة** (منها ١٢ صفحات أدوات مستثناة، فالباقي الحقيقي ٣٠ مقالاً).
  الأولوية بعد اليوم: `iqama-renewal-guide` (٧٨٤w)، `najiz-services-guide` (٧٨٠w)،
  `zatca-vat-e-invoicing-guide` (٧٦٢w) — ٣ حكوماتيات YMYL قريبة من الحدّ.
- **٩٧ مقالاً بلا جدول** — دفعة اليوم أضافت جداول لـ٣ مقالات فقط (common-prompt-mistakes،
  chatgpt-best-work-uses، effective-prompt-writing-rules)؛ الباقي محرّر لا سكربت.
- **`ads.txt`** موجود بالفعل بمعرّف `pub-3238758280300568` — الموقع مقبول لعرض AdSense الآن.
- **عمر الدومين**: ٢٠٢٦-٠٨-٢٩ → ٢٠٢٦-٠٩-١٢ = ١٤ يوماً — قابل للتقديم للسعودية.

## المسار المقترح

١. تقديم AdSense الآن — البنية والمحتوى جاهزان.
٢. المالك يشغّل الفهرسة (يفعلها بنفسه).
٣. أثناء المراجعة (٢-٤ أسابيع): توسّع ٣٠ مقالاً الباقية على نفس النهج (١٥-٢٠ دقيقة/مقال بمعدّل ٤-٥ مقالات/جلسة).

مرتبط: [[project_maqalat]] · [[project_maqalat_writing_playbook]] · [[content_guardrails_playbook]] · [[voice_bible]] · [[health_citation_sourcing]] · [[feedback_mdx_v3_comments]]
