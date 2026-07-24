---
name: security_hardening
description: الفحص الأمني والتحصينات المنشورة (CSP + إغلاق /docs) — لا تكسرها؛ التقرير في SECURITY_AUDIT.md
metadata:
  type: project
---

**فحص أمني كامل (2026-07-24، بتفويض المالك):** الوضع **قويّ** — صفر ثغرة حرجة/عالية. تأكّد أن التالي سليم فلا تُدخِل انحداراً: CORS مقفول، JWT `HS256` مع `algorithms=[HS256]` صريح (يمنع `alg=none`)، bcrypt، admin بـ`compare_digest`، **كل SQL بارامتري** (لا f-string بمدخلات مستخدم)، لا IDOR (الهوية من التوكن `user["id"]`)، rate limiting شامل (slowapi+Redis). التقرير الكامل: **`SECURITY_AUDIT.md`** بجذر الريبو.

**تحصينات منشورة — لا تكسرها:**
1. **CSP مفروض** في `dealpulseksa-web/next.config.mjs` (دالة `headers()`، متغيّر `csp`). **مُختبَر حيّاً: تسجيل الدخول/OTP + الصور + البيانات تشتغل.** لو أضفت مصدراً خارجياً جديداً (سكربت/صورة/API/iframe) **لازم تضيف نطاقه للـCSP** وإلا يُحجَب في المتصفّح. المسموح حالياً: `api.dealpulseksa.com` + `dealpulseksa-production.up.railway.app` (connect)، `res.cloudinary.com` (img/media)، Firebase/Google (`*.firebaseapp.com`/`*.googleapis.com`/`google.com`/`gstatic.com`)، Vercel (`*.vercel-scripts.com`/`vitals.vercel-insights.com`). `'unsafe-inline'/'unsafe-eval'` مُبقاة لسكربتات Next الداخلية (بلا nonce حفاظاً على ISR).
2. **`/docs` + `/openapi.json` مقفولان بالإنتاج** في `bot_app.py` (كانا يسرّبان مخطّط الـAPI). يُفتحان محلياً بـ`EXPOSE_DOCS=1` فقط. **لا تُعِد `docs_url="/docs"` ثابتاً.**
3. **COOP** (`same-origin-allow-popups`) ضمن رؤوس الأمان مع HSTS/XFO/nosniff/Referrer/Permissions.

**متبقٍّ (لوحات المالك، لا يُنفَّذ من الكود):** جدار الحافة — **Vercel Firewall** للويب + **Cloudflare Proxy (SSL=Full Strict)** على `api.dealpulseksa.com` لـWAF/DDoS (Railway بلا WAF). **Trusted Types مرفوض** (يكسر `dangerouslySetInnerHTML` لسكيما JSON-LD). راجع [[railway_deployment]] و[[website_project]].
