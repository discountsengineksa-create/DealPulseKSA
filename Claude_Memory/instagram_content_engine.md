---
name: instagram-content-engine
description: محرّك ريلز محتوى إنستقرام الفاخر + تنويع الكابشن + حالة حساب @dealpulseksa والأولويات
metadata: 
  node_type: memory
  type: project
  originSessionId: 00627dc4-16c9-4bf4-aeeb-45afe0de38c7
---

إنستقرام **@dealpulseksa** («كوبونات خصم نبض الصفقات») كان 45 منشور / **5 متابعين** — لأن الفيد ~100% منشورات كوبونات تلقائية (ترويج بحت لا يكبّر متابعين).

**بنينا (يونيو 2026):**
- `api/social/content_reels.py` — مولّد كاروسيلات محتوى **فاخر Dark Luxe** (1080×1350): خلفية زمردية-فحمية متدرّجة + لوقو + حاويات بظل + خط Noto (Cairo-Bold بالمستودع **لاتيني فقط** لا يدعم العربي). يعيد استخدام محرّك `ig_slides`. فيه `render_content_slides(concept)` + `render_image_slide(image,text,kicker)` + قائمة `CONCEPTS` (20 مفهوم نمو بلا رموز).
- تبويب **«🎬 ريلز المحتوى»** في dashboard.py (صفحة «استوديو المحتوى»): 3 أوضاع — مفاهيم جاهزة / اكتب مفهومك / صورة+نص. تنزيل ZIP أو شريحة.
- `api/social/template.py` — نوّعنا hook كابشن إنستقرام (`_pick` ثابت لكل متجر، متنوّع عبر الفيد).
- أضفنا إنستقرام لـsameAs (lib/seo/constants.ts بريبو الويب).

**موجود مسبقاً:** نظام نشر إنستقرام كامل (Meta Graph API + `InstagramPoster` + `reels_video` = صورة→MP4 ثابت عبر Cloudinary). **التوكن سرّ بالإنتاج (مو متاح لي) فما أقرأ insights**.

**معلّق:** الستوريات التلقائية وقفت (المستخدم بلّغ) — يُرجّح توكن Meta منتهي؛ **لم يُشخَّص بعد**.

**الاستراتيجية:** السوشال = محرّك المتابعين؛ الفيد يحتاج ~65% محتوى نمو (نصائح/تفاعل/مواسم/ثقة) لا 100% كوبونات. القيود: لا رموز في الريلز · عربي سعودي · يربط [[marketing_skills_toolkit]] (social) و[[affiliate_ppc_brand_restrictions]].
