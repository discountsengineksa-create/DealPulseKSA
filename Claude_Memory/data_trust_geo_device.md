---
name: data-trust-geo-device
description: City/country/device fields — which are real vs hardcoded fakes; never trust bot_users.city for analytics
metadata: 
  node_type: memory
  type: project
  originSessionId: 1852a4cb-f634-46c7-bb76-a04947c91d64
---

مصيدة بيانات حرجة لأي تحليل جغرافي/أجهزة (اكتشفت 2026-06-05):

**مزيّفة بالكود — ممنوع استخدامها في التحليل:**
- `bot_users.city` = ثابت `'الرياض'` لكل مستخدم بوت، يُكتب وقت اختيار اللغة في `deal_pulse_bot.py` (`_LANG_DEFAULTS` ~سطر 1463-1490). لا تُقاس أبداً.
- `bot_users.country` = ثابت `'المملكة العربية السعودية'`.
- `bot_users.device_type` = `'iPhone' if is_premium else 'Android'` — تخمين من اشتراك تيليجرام بريميوم، مو كشف جهاز.
- الداشبورد القديم يعرفها كذبة: `dashboard.py:3320` فيه تعليق `# bu_city افتراضية فلا نعتمدها`.

**حقيقية:**
- `web_users.city` = المستخدم يختارها من قائمة بصفحة التسجيل (`dealpulseksa-web/app/register/page.tsx`). القيمة دائماً عربية canonical بالتصميم (value=عربي، label حسب لغة الواجهة). القيم الإنجليزية مثل "Riyadh" = حسابات اختبار (Verify Test / verify-fresh@example.com) دخلت عبر API بتجاوز النموذج.
- `action_logs` فيه طبقة إثراء جغرافي كاملة من IP وقت نقر تحويل `/go` (Cloudflare Worker، migration_010): الأعمدة `city, region_code, country_code, postal_code, lat, lng, accuracy_km, isp, asn, is_datacenter, is_proxy, device_class, cf_bot_score, quality_score`. هذا المصدر الحقيقي الوحيد لجغرافيا البوت/الميني.

**مُثبت (مستخدم 305081756 asiri_l):** `bot_users.city`='الرياض' (مزيّف)، لكن `action_logs.city`='Dammam' في 3 صفوف فقط من 349 (الباقي NULL). أي الجيو يُلتقط فقط لحظة نقر /go، فالتغطية **جزئية** (المستخدم يلزمه نقرة زيارة متجر واحدة على الأقل عشان نعرف مدينته).

**القاعدة للتحليل الجغرافي:** المصدر الوحيد `action_logs` (city/region_code/country_code)؛ خذ آخر قيمة غير-NULL لكل مستخدم؛ افلتر `is_proxy=false AND is_datacenter=false`؛ اعرض «تغطية X من Y» بصراحة. لا `bot_users.city` أبداً. وللجهاز: `action_logs.device_class` حقيقي، لا `bot_users.device_type`. (تصحيح سابق: صلاح/فراس/يوسف أشخاص مختلفون فعلاً، لا ازدواج عبر المنصات). مرتبط بـ [[bug_fixes]] ومبدأ صفر-فبركة في [[analysis_rebuild_strategy]].

**سلسلة الجيو الكاملة (مهم):** المتصفّح لازم ينادي `api.dealpulseksa.com` (خلف CF+Worker) لا أصل Railway المباشر. الموقع على **Vercel** (مشروع `dealpulseksa-web`، دومين www.dealpulseksa.com)، ومتغيّره `NEXT_PUBLIC_API_URL` لازم = `https://api.dealpulseksa.com/api/v1` (كان railway-direct فيتجاوز الـWorker → city/country=NULL؛ صُحّح 2026-06-22 + Redeploy؛ NEXT_PUBLIC_ يُخبَز وقت البناء فيلزم إعادة بناء). ملاحظة: متغيّر NEXT_PUBLIC_API_URL على خدمة Railway (الـAPI/FastAPI) عديم الأثر — Vercel فقط. وتوحيد بصمة الزائر يتطلّب visitor_id على **كل** حركة: /go عبر buildGoUrl &v= (go.py يخزّنه)، و/track عبر trackAction؛ كان CopyButton (نسخ صفحة المتجر) يرسل fetch مباشر بلا visitor_id فيُعطى الزائر بصمتين (visitor_id للمشاهدة/النقر، ip_hash للنسخ) ⇒ صفّان — صُحّح بإضافة getVisitorId() (commit b3e5fa3).

**تحديث 2026-06-22 (مُحلّ ✅):** الجيو رجع حيّاً — أُعيد نشر الـ Worker بعد تصحيح ORIGIN_BASE→أصل Railway (`https://dealpulseksa-production.up.railway.app`) + `wrangler secret put IP_HASH_SALT` + `wrangler deploy` (الـ routes الثلاثة مربوطة: /api/v1/track, /track/*, /go/*). probe عبر api.dealpulseksa.com أعاد city=Riyadh + ip_hash + country=SA + asn. الملح يومي التدوير (بصمة IP تتغيّر كل يوم) فالتمييز عبر الأيام يعتمد visitor_id. النشر يدوي بصلاحية Cloudflare (حساب discountsengineksa@gmail.com). أدناه سياق العطل السابق:

**كان (قبل الإصلاح) — الجيو متوقّف (انحدار في الـ Worker):** `action_logs` الحالي مُصفَّر (~117 صفّاً) و**0 صفّ فيه city أو ip_hash** عبر كل المصادر. الـ API خلف Cloudflare (CF-RAY موجود) لكن worker `dealpulse-edge-enrichment` (مجلد `cloudflare-worker/`) لا يُثري `/track*` و`/go/*` → لا x-dp-*. سبب مرشّح: `wrangler.toml` سطر 28 `ORIGIN_BASE` مكسور (اقتباسات متداخلة + يشير لـ api.dealpulseksa.com نفسه = حلقة)؛ يجب أن يشير لأصل Railway. لإعادة المدينة: أصلح ORIGIN_BASE→أصل Railway + `wrangler secret put IP_HASH_SALT` + `wrangler deploy` + تأكيد الـ route في CF. **هوية الزائر المجهول الآن لا تعتمد الجيو:** `visitor_id` (localStorage) يُمرَّر على كل حركة بما فيها نقرات `/go` (commit 286355e go.py + 8e6bff1 web)، وأضفنا fallback لـ `ip_hash` من cf-connecting-ip/x-forwarded-for في `geo_extractor` (IP_HASH_SALT). الداشبورد يُفضّل visitor_id ثم ip_hash. لكن **المدينة** تظل فارغة للمجهول حتى يُصلَح الـ Worker — لا تُفبرك.
