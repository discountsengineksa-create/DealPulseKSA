---
name: Maqalat AI Cluster + Site Hardening 2026-09-11
description: عنقود AI ~150 مقال (18 باتش) + تنظيف AI-slop شامل + إصلاح Ahrefs P0 (500/404/hreflang/meta) + ISR + lazy-load — إجمالي 228+ مقال، السايت ماب 252 URL
type: project
originSessionId: 50c79b58-a628-4082-9362-c72760b9bc41
---
**التاريخ:** 2026-09-11 (بعد نحو أسبوع من أول إطلاق للعنقود).

**البنية النهائية للعنقود:**
- 18 باتش (a892392..3edcda6) — ابتدأ بـ12 مقال إطلاق ثم دفعات 10 مقال في المتوسط.
- تغطية: تأسيسات (LLM/Transformers/MCP)، أدوات (ChatGPT/Gemini/Claude/Copilot/Grok)، عمالقة الشركات، Verticals (طبي/تعليمي/قانوني)، Snippets (JS/HTML/Python)، Meta-prompting، AutoGen/CrewAI، MLOps، AI السعودي (HUMAIN)، أخلاقيات/محاذاة.
- كل المقالات AR + غالبيتها EN sibling.

**تنظيف AI-Slop (3 مراحل):**
1. `c267ff7` — مسح P0 على 228 مقال كامل.
2. `597d129` — إعادة كتابة سردية لأسوأ 10 مقالات.
3. `541c416` — تحويل 111 افتتاحية FAQ من ترقيم آلي إلى نثر طبيعي.
4. `3b62f74` — تنظيف نهائي على 21 مقال.

**إصلاح Ahrefs P0 (5 موجات):**
- `0b17e2c` — 9 صفحات 500، /en/en 404s، /about build error.
- `72c3147` — 268 صفحة /blog/{slug} 404 (redirect دائم).
- `22fb880` — h1 مكرّر، meta lengths، OG، hreflang.
- `24cf242` — 178 صفحة /en 404 + OG على 12 صفحة static.
- `721da1c` — تعطيل next-intl auto Link-header hreflang (المصدر الحقيقي للـ178).

**تحسين الأداء:**
- `efee53d` — ISR (revalidate 3600) على homepage + cluster pages.
- `cfa7202` — تقليص RSC payload + ISR على مقالات + توزيع inbound inlinks.
- `230db8f` — نقل `<html>` خارج root layout لتمكين ISR على 265 صفحة.
- `a3ca4e2` — lazy-load مكونات below-fold + هجرة middleware → proxy.

**التحقّق في الإنتاج (2026-09-11):**
- الرئيسية: 200، X-Vercel-Cache HIT، Age 2743s، X-Nextjs-Prerender: 1 ✅
- /en: 200 ✅
- /blog: 404 = صحيح (المشروع كله `/c/{cluster}/{slug}`، لا وجود لـ/blog)
- Sitemap: 252 URL

**الحالة الحالية:**
- محتوى: 228+ مقال جاهز.
- تقني: Ahrefs P0 نظيف، ISR شغّال.
- إندكسنق: 200 URL دُفعت اليوم، 52 متبقّية للحصّة اليومية.
- التالي: AdSense resubmission (كل عوائق الرفض السابقة رُفعت) + عناقيد جديدة من `project_maqalat_competitor_landscape.md`.
