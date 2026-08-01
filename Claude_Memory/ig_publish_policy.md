---
name: IG Publishing Policy (Stories Manual, Reels Auto-Every-6)
description: قرار 2026-06-19 — الستوري التلقائية ملغاة على إنستقرام، والريل يُنتَج تلقائياً بعد كل 6 بثّات
type: project
originSessionId: 8ad06fba-06cb-4d18-a88b-e16ec326d304
---
قرار 2026-06-19 لمحرّك نمو إنستقرام في DealPulseKSA:

**الستوري التلقائية ملغاة** — الكود محذوف من `api/social/dispatcher.py:_broadcast_to_instagram`. المالك ينشر الستوريات يدوياً من تطبيق إنستقرام بدل من البوسترات المربّعة الأوتوماتيكية.

**الريل التلقائي يبقى نشطاً** — بعد كل بث ناجح، يُعاد `master.last_reeled_at = NULL` للمتجر الحالي، ثم يُستدعى `run_pending_batches(conn)`. النتيجة: كل ٦ بثّات تراكمياً = ريل تلقائي واحد بـ٦ متاجر.

**Why:** المالك جرّب الستوري الأوتوماتيكية واكتشف:
- البوستر المربّع كان يخرج فاضي (أصلحناه لـ٩:١٦)
- حتى مع الإصلاح، يفضّل التحكّم اليدوي بمحتوى الستوري (نصوص/stickers/تفاعل)
- الريل الجماعي ذو القيمة الأعلى (٦ متاجر × 30 ثانية) يستحق الأتمتة

**How to apply:**
- لا تُعد إضافة `post_story` للـdispatcher التلقائي
- لو احتاج المالك ستوري تجريبية، الـendpoint `POST /api/v1/admin/social/test-story/{master_id}` يبقى متاحاً للاختبار اليدوي
- الـspec `instagram_story = 1080×1920` في `image_specs.py` يبقى للاستعمال اليدوي عبر الـendpoint
- لا تُغيّر منطق إعادة `last_reeled_at=NULL` في dispatcher — هو اللي يضمن استمرار «كل 6 = ريل»

**🔎 تشخيص «ليش المتجر ما انرسل لإنستقرام؟» (2026-08-02):** السؤال يتكرّر، والجواب غالباً **ليس عطلاً**:
- منذ **2026-07-15** المسار **Reels-only**: `IG_AUTO_FEED_ENABLED` مطفأ افتراضياً، فالـdispatcher **لا يُدرج صف `instagram` أصلاً** في `social_posts_log` (لا sent ولا failed ولا skipped). المتاجر القديمة (ديزل/سبورتر/بيد إن روم، يوليو ١٢-١٤) لها صفوف `instagram=sent` لأنها تسبق التغيير — فلا تقارن بها.
- **التحقّق الصحيح** يكون على `platform='instagram_reel_batch'` وعلى `master.last_reeled_at`، لا على صف `instagram`.
- مثال محسوم: عبدالصمد القرشي (id 56) **نُشر فعلاً** ضمن ريل ١ أغسطس 18:12 (post id 18186424936397482) مع ايجنر وبيد إن روم وسبورتر وديزل ووولفيكس. أما شفق الشرق (id 58) فهو **الوحيد المنتظر** (`last_reeled_at IS NULL`) والريل يحتاج **٦** — وسياسة المالك بالكود: «نظبر للسادس حتى لو شهر».
- **أعطال جانبية قائمة (غير إنستقرام):** X يرجع `HTTP 401` (توكن منتهٍ) و Threads يرجع `create HTTP 500` في كل البثّات الأخيرة.

**استعلام التشخيص الجاهز:** `SELECT master_id, platform, status FROM social_posts_log WHERE master_id=<id>` + `SELECT id, store_id FROM master WHERE last_reeled_at IS NULL`.
