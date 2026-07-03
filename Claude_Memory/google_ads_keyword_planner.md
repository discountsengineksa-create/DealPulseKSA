---
name: google_ads_keyword_planner
description: تكامل Google Keyword Planner في «محرك الفرص» — الحسابات، حالة Basic Access، مكان المتغيّرات
metadata: 
  node_type: memory
  type: project
  originSessionId: 61c1bcf7-09f5-4fff-bf12-77d11745e663
---

تكامل **Google Ads API → Keyword Planner** (حجم البحث الشهري + المنافسة) في «🎯 محرك الفرص». مكمّل لـ Google Trends (شعبية نسبية فقط). الموديول `api/seo/keyword_planner.py` (REST مباشر، بلا مكتبة google-ads).

**الحسابات (تحت إيميل `discountsengineksa@gmail.com`):**
- حساب Google Ads عادي: `830-423-1088` — **غير مربوط** تحت الإداري (يعطي CUSTOMER_NOT_FOUND).
- حساب إداري (MCC): `857-047-5609` — **نستدعيه مباشرة** كـ `GOOGLE_ADS_CUSTOMER_ID=8570475609`، بدون `login-customer-id`.
- إصدار API: **v21** (v17-v19 مسحوبة → 404). افتراضي الموديول v21.

**⛔ حالة الاعتماد: مرفوض نهائياً (2026-06-09).** رد `ads-api-compliance@google.com`: *«Tools that offer only keyword research are not allowed by the Google Ads API Policy»* — سياسة RMF (الحد الأدنى من الوظائف): الـ API لا يُعتمد لأداة بحث كلمات فقط، لازم إدارة حملات/تقارير فعلية. احنا مجمّع كوبونات لا ندير حملات → **الرفض سياسة لا خطأ طلب**. إعادة التقديم بنفس الغرض = نفس الرفض؛ الالتفاف = كذب على Google (يكسر White-Hat). **الموديول `keyword_planner.py` يبقى يرجّع `{}` بهدوء (Test token).**

**القرار المعلّق (2026-06-09):** إما (أ) حذف تكامل الحجم والاكتفاء بـ Google Trends (SerpApi) للأولوية — مجاني، أو (ب) مصدر حجم بحث طرف-ثالث (Keywords Everywhere / DataForSEO) — أرقام حقيقية بلا موافقة Google، تكلفة بسيطة. لا نترك العمود يعرض «—» للأبد (يخالف [[feedback_no_dead_code]]).

**المتغيّرات (5):** `GOOGLE_ADS_DEVELOPER_TOKEN / CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN / CUSTOMER_ID` — في `.env` المحلي + خدمة **DEALPULSEKSA** على Railway (هنا يشتغل الكود؛ الداشبورد لا يحتاجها لأنه يقرأ عبر الـ API). OAuth: تطبيق منشور للإنتاج (refresh token لا ينتهي).

**الكود:** migration_042 (أعمدة `avg_monthly_searches`/`competition`/`kw_volume_checked_at` على `seo_opportunity_keywords`)؛ endpoints `/seo-opportunities` refresh + refresh-all يجلبان الحجم (دفعات 20)؛ الداشبورد يعرض شارة «بحث/شهر». السياق الكامل في [[seo_white_hat_only]].
