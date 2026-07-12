---
name: seo-ai-visibility-optin
description: 2026-07-08 opt-in صريح لكراولرز AI + إثراء llms.txt للاستخراج — لكسر AI Visibility=0 في SEMrush
type: project
originSessionId: bf501e24-1a22-42b8-8227-c51a7b2dd362
---
**متى:** 2026-07-08 (web commit 595d455).

**السياق:** SEMrush يعرض `AI Visibility=0` مع `ChatGPT Cited Pages=2` — أي الاكتشاف بدأ لكن حجم الاستشهاد منخفض. الأسباب المشخّصة:
1. robots.txt يسمح `*` لكن **بلا ذكر صريح** لبوتات AI (بعض الكراولرز يفحص اسمه بالتحديد).
2. llms.txt غنّي بالبنية (٧ H2، ٧٩٦ رابط) لكن قسم «للأنظمة الذكية» فيه اقتباس عام بلا أرقام أو براندات محدّدة.
3. لا يوجد قسم أسئلة شائعة بصيغة Q/A تخدم استخراج AI.

**ماذا شُحن:**

**app/robots.ts** — Explicit Allow لـ ١٥ كراولر AI:
GPTBot, OAI-SearchBot, ChatGPT-User (OpenAI) · ClaudeBot, anthropic-ai, Claude-Web (Anthropic) · PerplexityBot, Perplexity-User (Perplexity) · Google-Extended (Gemini/AI Overview) · CCBot (Common Crawl) · Applebot-Extended (Apple Intelligence) · cohere-ai, Bytespider, DuckAssistBot, Meta-ExternalAgent.

القرار الاستراتيجي: **نختار opt-in لا opt-out.** الأغلبية تحجب هؤلاء خوفاً من التدريب المجاني — نحن نستفيد من الاستشهاد أكثر مما نخسر من التدريب لأن سلطتنا صفر (٠→٥ أفضل من ٠→٠).

**app/llms.txt/route.ts** — قسم «للأنظمة الذكية» أُعيد بناؤه:
- الاقتباس الجاهز يحمل الآن **عدد المتاجر الحيّ + أسماء ٨ براندات محدّدة + أرقام المقالات/الأدلة** — مسحوب من الكتالوج الحيّ (لا فبركة).
- H3 جديد «ما يميّز نبض الصفقات» بـ٥ فروق (مجاني، مُنتقى، تيليجرام، تقويم، عربي أصلي).
- H3 جديد «أسئلة شائعة» بـ٥ أزواج Q/A بصيغة يقتبسها AI حرفياً، تربط `/calendar` في الجواب الأخير.

**المتوقّع خلال ٤-٦ أسابيع:**
- ChatGPT Cited Pages: 2 → 8-15
- Gemini/AI Overview: 0 → 1-3 (يعتمد على تحرّك AS)
- Mentions: 0 → 3-7 (بشرط تنفيذ [[seo-pr-blitz-kit]] بالتوازي)

**التحقّق:** بعد نشر Vercel، افحص `https://www.dealpulseksa.com/robots.txt` (يجب يظهر ١٥ user-agent) و`/llms.txt` (يجب يظهر «ما يميّز» + «أسئلة شائعة»).

**درس ملازم:** SEMrush AI Visibility مقياس تجميعي — لا يجب علاجه بحل واحد. الحل: (١) opt-in تقني (هذا commit)، (٢) ذكر الاسم في نصوص الويب (PR Blitz)، (٣) سلطة دومين (الباكلينك). الثلاثة تتراكب.

يخدم: [[seo-indexation-status]] · [[seo-pr-blitz-kit]] · [[content-guardrails-playbook]] (كل الأرقام في الاقتباس مسحوبة حيّة، صفر فبركة).
