---
name: web_visits_tracking
description: نبض الزوّار — تتبّع زيارات الموقع على مستوى الجلسة (web_visits / Migration 060) منفصل عن action_logs
metadata: 
  node_type: memory
  type: project
  originSessionId: a5366cbe-94bf-4696-8923-0ea97d18e4a5
---

الموقع لم يكن يسجّل «الزيارات» إطلاقاً: الداشبورد يقرأ المسجّلين (web_users) + الأحداث الصريحة (action_logs: نسخ/نقر/بحث) فقط، فمن يتصفّح ويطلع كان مخفياً. أضفنا تتبّعاً **على مستوى الجلسة** (صف واحد لكل زيارة لا لكل صفحة):

- **web (dealpulseksa-web):** `trackVisit()` في [[reconcile_web_repo_separately]] lib/api.ts (dedupe عبر sessionStorage `dpk_visit_id`) + مكوّن `VisitTracker` صامت مُركّب في app/layout.tsx. يُطلق ping واحد لكل جلسة → `POST /track/visit`.
- **API:** endpoint `/track/visit` في api/routers/track.py (يُثري الجغرافيا+الجودة من نفس مسار action_logs، `_classify_referrer` يصنّف المصدر search/social/direct/internal/referral بمطابقة حدّ-نقطة لتفادي substring الخاطئ). schema `VisitRequest` في api/schemas/track.py.
- **DB:** جدول `web_visits` (Migration 060) — `visit_id UUID UNIQUE` (idempotent)، user_id FK→web_users، referrer_kind/host، landing_path، إثراء جغرافي + `quality_score`. **Migration 061** أضاف `visitor_id UUID` (بصمة متصفّح ثابتة من localStorage، key `dpk_visitor_id`) لتمييز العائدين عبر الجلسات/الأيام حتى لو تغيّر الـ IP.
- **Dashboard:** صفحة جديدة «👣 زوّار الموقع» ضمن قائمة التحليل (مستقلّة عن فلاتر «تحليل المستخدمين») + قسم «🔁 الزوّار والعائدون»: فريدون/عائدون/نسبة العودة + أكثر الزوّار تكراراً + سجل خام. الهوية بالأولوية: `user_id ← visitor_id ← ip_hash`.

**سيريل الجهاز مستحيل:** الويب لا يقدر يقرأ سيريل/IMEI/MAC (حظر متصفّح). `visitor_id` (UUID بـlocalStorage) هو البديل القياسي الوحيد المشروع. fingerprinting (شاشة/كانفس) مرفوض (يتعارض White-Hat).

**هدف المالك: «المجهول يُعرف داخل الأقسام الموجودة كمستخدم»** (الموقع مفتوح للكل بلا إجبار تسجيل لكسب الترافيك؛ التسجيل يرجع لاحقاً عبر toggle `web_login_gate_enabled` في «إدارة الموقع»). لا صفحات/جداول موازية — التعرّف داخل الأقسام نفسها. مشروع 4 مراحل:
- **م1 ✅ منشور:** `getVisitorId()` يُرسل البصمة مع كل حركة (trackAction/trackCategoryView/logSearch) → `action_logs.visitor_id` (Migration 062). و«تحليل المستخدمين» يضيف realm رابع `anon` (هوية=visitor_id، سلوك كامل، حقول الملف فاضية) يظهر بعرض الكل/الموقع بلا فلاتر شخصية. الهوية بالأولوية `COALESCE(user_id, visitor_id, ip_hash)`.
- **م2 (متبقّي):** فتح المفضلة للمجهول (`user_favorites.visitor_id` + يفضّل بلا تسجيل).
- **م3 (متبقّي):** فتح الستوري للمجهول (`story_views.visitor_id` + يشوف بلا تسجيل) — حالياً logStoryView يتخطّى المجهول.
- **م4 (متبقّي):** توحيد الهوية في تحليل المتاجر/الأقسام/الترند (عدّ unique بـ COALESCE).

ملاحظة: `direct_search` ما فيه visitor_id بعد → بحث المجهول يُربط عبر action_logs(action_type='search') فقط.

**Why:** شكوى المالك «ناس مرّت أمس وما ظهرت بأي تحليل» — لأن الزيارة الخام لم تُسجَّل. Vercel Analytics يلتقطها لكن خارج الداشبورد وبلا ربط ببيانات المتاجر/المستخدمين. يكمّل [[data_trust_geo_device]] و [[users_analytics_rules]].

**How to apply:** البوتات مفلترة افتراضياً `quality_score >= 50` (toggle «يشمل البوتات» للكل). web_visits ≠ action_logs — لا تخلط العدّ. **ترتيب النشر إلزامي:** طبّق Migration 060 على Railway *قبل* نشر الـ API، وإلا كل /track/visit يطيح 500 (INSERT على جدول غير موجود) — الصفحة بالداشبورد تكشف غياب الجدول وتعرض أمر التطبيق.

**⚠️ تسرّب زواحف Meta/Apple (2026-07-29):** فلتر `quality_score>=50 AND is_datacenter IS NOT TRUE` **لا يكفي** — `cf_bot_score` فارغ تماماً (Cloudflare bot-score غير مفعّل)، وكثير من IPs السحابية غير مُعلَّمة `is_datacenter`. النتيجة: زواحف **Meta/Facebook (ASN 32934، Ashburn)** و**Apple/Applebot+prefetch (ASN 714، Leesburg/Seattle)** تمرّ كـ«بشر» وتُضخّم العدّاد بلا أي نقر/نسخ → توهم أن الترافيك أمريكي. الحقيقة: على مستوى الأفعال (action_logs) **السعودية هي الجمهور المتفاعل الأول** (78 فعل/30ي مقابل US=11 بصفر نقر/نسخ). **الإصلاح:** أُضيف `AND (asn IS NULL OR asn NOT IN (32934, 714))` إلى فلتر «زوّار الموقع» (ثابت `_CRAWLER_ASNS`) — خفّض عدّاد 30ي من 1147→441 وقلب ترتيب الدول لـ SA أولاً. **درس:** لتقييم «بشر حقيقي» استخدم action_logs (نقر/نسخ يتطلّب إنسان) لا web_visits الخام؛ ولا تحكم على الجغرافيا من نطاق يوم واحد (لقطة «صنعاء+تورنتو» كانت فِعلَين فقط). [[bot_vs_promo_heuristic]] · [[marketing_baseline_and_strategy]]
