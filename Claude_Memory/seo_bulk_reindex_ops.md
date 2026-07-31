---
name: seo_bulk_reindex_ops
description: كيف تدفع روابط بالجملة لـIndexNow+Google (endpoint، سقف CF 100s، حصة Google 200/يوم)
metadata: 
  node_type: memory
  type: reference
  originSessionId: ec8d5721-db2e-4dab-8fa0-0d0cafe5c88e
  modified: 2026-07-28T16:50:11.329Z
---

دفع الفهرسة بالجملة بعد تحديث محتوى كبير (مثلاً إعادة كتابة عناقيد المدوّنة).

**الـendpoints (باكند Railway):**
- بالجملة: `POST https://api.dealpulseksa.com/api/v1/admin/reindex-urls` body `{"urls":[...]}` (سقف 50/نداء داخلياً).
- مفرد: `POST .../admin/seo-resubmit-url?url=<URL>` (سكربت `seo/ping_indexnow.ps1`).
- الهيدر: `X-Admin-Secret: <ADMIN_SHARED_SECRET من .env>`. كلاهما يدفع IndexNow (Bing/Yandex/Naver/Seznam) **و** Google Indexing API معاً، best-effort، يُسجَّل في `seo_index_submissions`.

**درسان تشغيليان مهمّان:**
1. **سقف Cloudflare ~100s على النداء** → 50 URL/نداء يتجاوزها فيرجع **524** (edge timeout) بينما الأصل يكمل فعلاً. **استخدم ≤25 URL/نداء** (~70s) للحصول على تأكيد فعلي. النطاق القانوني هو `https://www.dealpulseksa.com` (SITE_URL بـwww، لا apex).
2. **حصة Google Indexing API ~200/يوم/مفتاح** → بعد ~200 تصير النتيجة `429`. IndexNow **بلا حصة** وهو إشارة الزحف السريعة الموثوقة → ادفع كل الروابط له، ووزّع Google على أيام (الحصة تتجدد يومياً). أداة PowerShell تحتاج chunk=25 و`-TimeoutSec 110` و try/catch لكل chunk.

**مطبّان يمنعان النداء من عميل سكربت (2026-07-31):**
1. **Cloudflare يردّ 403 «error code: 1010»** على أي عميل ببصمة غير متصفّح (urllib/requests الافتراضي)
   — جدار الحافة من [[security_hardening]]. **الحل: أرسل `User-Agent` متصفّح كامل** مع
   `Accept`/`Accept-Language`. السرّ في الهيدر صحيح ولا علاقة له بالرفض.
2. **`CERTIFICATE_VERIFY_FAILED: certificate has expired`** من بايثون محلياً = **جذر CA قديم في
   مخزن الجهاز**، لا شهادة منتهية على الخادم. تحقّقت: شهادات الإنتاج Let's Encrypt سارية
   (api حتى 2026-10-05، www حتى 2026-10-07). **الحل: `ssl.create_default_context(cafile=certifi.where())`** —
   ولا تعطّل التحقّق (`CERT_NONE`) قبل إثبات أن الشهادة سليمة فعلاً.

**تذكير الصراحة ([[content_guardrails_playbook]]):** IndexNow/Indexing API = طلب زحف، **ليس ضمان فهرسة**. العنق الحقيقي سلطة الدومين/الباكلينك ([[seo_indexation_status]] · [[seo_authority_building]]) لا كمّ الدفع. راجع [[seo_google_indexing_live]].
