---
name: Project Maqalat
description: مشروع مستقل جديد (2026-08-29) — مدوّنة مرجعية شاملة عربي/إنجليزي؛ maqalat.org على Cloudflare؛ هدف Google AdSense
type: project
originSessionId: a9e30f87-7dcb-4296-950a-248d6bd790d5
---
## الأساسيات المؤكّدة

- **Domain**: `maqalat.org` (Cloudflare Registrar، $8.50/سنة ثابت) — **حيّ منذ 2026-08-30**
- **Email المخصّص**: `maqalatorg@gmail.com`
- **تاريخ التسجيل**: 2026-08-29
- **Repo محلياً**: `C:\Users\user\Desktop\maqalat\` — GitHub: `maqalatorg/maqalat`
- **Vercel Project**: `maqalatorg/maqalat` (Hobby)
- **Stack**: Next.js 15 + App Router + MDX + Tailwind + Vercel + Cloudflare DNS
- **DNS Setup**: CNAME `@` و `www` كلاهما → `3f8648f8af4a0dcf.vercel-dns-017.com` (Vercel new IP range، Proxy = DNS only إجباري لأجل SSL)
- **Routing**: apex = Production، www = 308 → apex
- **SSL + HSTS**: مفعّلَين تلقائياً عبر Vercel
- **Firebase Project**: `maqalat-org` (Spark plan، Analytics معطّل، Gemini in Firebase مفعّل)
- **Firestore Location**: `me-central2 (Dammam)` — Saudi Arabia region (~5-15ms latency للسعودية، السيادة على البيانات محلياً، نفس تسعير Regional). **مقفل نهائياً**.

## المفهوم

مدوّنة شاملة عربي (رئيسي) + إنجليزي، محتوى مرجعي واقعي 100% بلا فبركة. مواضيع مخطّط لها: صحة، ماليات، سيارات، جامعات، تقويم/مناسبات، شروحات (نظام نور، تطبيقات)، مواقع، أقمشة، أسهم، عملات رقمية.

## الاستراتيجية المتفق عليها

- **البداية**: عنقودان محليان منخفضا المنافسة → **تقويم/مناسبات سعودية** + **جامعات سعودية** (فهرسة سريعة، منافسة أضعف، بحث كثيف)
- **الحصاد** (~٣ شهور): توسّع مرحلي للصحة/المال/السيارات
- **AdSense كأولوية**: يتطلب ٢٠-٣٠ مقال + About/Privacy/Contact + دومين عمره أسبوعين+، مراجعة ٢-٤ أسابيع
- **YMYL Standard**: كل ادعاء بمصدر رسمي (Harvard/NIH صحياً، هيئة السوق للاستثمار، الجهات الرسمية للتسجيلات) — نفس قاعدة نبض الصفقات

## Why (سبب المشروع)

- مصدر دخل ثاني مستقل عن نبض الصفقات (كوبونات)
- تنويع محفظة الإيرادات
- اختيار اسم `maqalat` وصفي بذاته — يحلّ مشكلة «نبض الصفقات = كوبونات» التي كانت تتطلب شرحاً دائماً للمستخدم

## How to Apply

- كل شغل SEO **White-Hat فقط** (نفس القاعدة الحاكمة لكل المشاريع)
- طبّق **Content Guardrails Playbook**: صراحة استراتيجية، لا فبركة، مصادر رسمية، ربط داخلي متبادل، تنسيق للجهازين
- الروابط الخلفية بين maqalat و dealpulseksa مسموح ومطلوب (استراتيجية جوابه للأولية)
- قبل تقديم AdSense: About/Privacy/Contact + ٢٠ مقال أصلي + دومين ≥ أسبوعين
- تكامل Google Search Console + Analytics + IndexNow من اليوم الأول (تعلّمنا من نبض الصفقات)
