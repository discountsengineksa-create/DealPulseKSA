---
name: Instagram Growth Engine (Carousel + Story + Reel + SEO captions)
description: How Instagram broadcast works after the 2026-06-19 rewrite — per-platform captions, 2-slide carousel, auto-story, optional Reel, comprehensive keyword bank
type: project
originSessionId: 79fe7e7d-9e07-481c-a8e4-e7eac1772866
---
أعيد هندسة مسار النشر على إنستقرام في `2026-06-19` لاستهداف الهيمنة على البحث السعودي.

**Why:** المالك يريد كل من يبحث عن «كوبون / كود / خصم / عسل / عبايات / ملابس...» يجد الحساب. النشر السابق كان صورة ثابتة + caption عام + 7 هاشتاقات تنافسية فقط = صفر تحويل (الرابط داخل الـcaption ميت على إنستقرام).

**How to apply:**
- **caption إنستقرام** يُبنى من `build_post_text(store, platform='instagram')` في [`api/social/template.py`](api/social/template.py). يحتوي:
  - Hook: «كود خصم {name} — {discount} 🔥» (أول سطرين قبل «عرض المزيد»)
  - CTA: «الرابط في البايو» (لا رابط مباشر — Instagram يكسره)
  - 28 هاشتاق من `CATEGORY_KEYWORDS` (~30 فئة سعودية) + `REGIONAL_HASHTAGS` (مدن) + `EVERGREEN_HASHTAGS` + متغيرات اسم المتجر
- **تطبيع التاقات**: `_normalize_tag` يوحّد همزات الألف (أ إ آ → ا) + ى→ي + ة→ه — DB يحتوي «ازياء» و«أزياء» كصفّين، كلاهما يحلّ لنفس مفتاح القاموس.
- **الـDispatcher** ([`api/social/dispatcher.py`](api/social/dispatcher.py)) يستدعي `_run_instagram_extended` بدل `_run_one_poster` لـInstagramPoster — يبني Carousel (Slide 1 = `social_poster_url`، Slide 2 = how-to slide مولَّدة بـPIL+arabic_reshaper من [`api/social/ig_slides.py`](api/social/ig_slides.py) ومرفوعة Cloudinary بـpublic_id `store_posters/{slug}_howto`)، ثم Story تلقائياً، ثم Reel لو `master.reels_video_url` معبّأ أو لو يقدر يولّد رابط Cloudinary `du_5,f_mp4`.
- **الـlog**: `social_posts_log` يسجّل صفوف منفصلة بـplatform `instagram` / `instagram_story` / `instagram_reel`.
- **Reels MP4 (batch)**: التصميم الحالي = **6 متاجر/Reel** (LIFO). آلية:
  - `claim_reel_batch` ([`api/social/reels_batch.py`](api/social/reels_batch.py)) يحجز 6 متاجر بـ`SELECT … FOR UPDATE SKIP LOCKED` (atomic، آمن للبث المتزامن).
  - `render_batch_mp4` يولّد MP4 1080×1920 (Reels-spec) 30s 30fps H.264 بـimageio-ffmpeg. اختُبر محلياً: 5MB في 27s.
  - `run_pending_batches` تُستدعى من `_run_instagram_extended` بعد كل بث ناجح: ما دام عدد المنتظرين ≥ 6 → تنتج Reel. لو 12 → 2 ريلز متتاليين. لو 5 → تنتظر السادس بصمت.
  - حد أقصى 3 ريلز/تشغيل واحد (حماية من spam-trigger).
  - الفشل يُعيد المتاجر للقائمة (`_release_batch`) — لا نخسر متجراً في reel فاشل.
- **الصوت**: MP4 يخرج صامتاً. Instagram Graph API لا يعطي الترند السعودي (قرار Meta). لتفعيل موسيقى ثابتة: ضع MP3 في `audio/` + `REELS_AUDIO_PATH` env. NOT IMPLEMENTED YET في render — مكان التوسيع داخل `imageio.get_writer`.

**migrations يجب تطبيقها على Railway:**
- `migration_058_master_reels_video.sql` — يضيف `master.reels_video_url` (legacy — غير مستعمل في النظام الجماعي الحالي، يبقى للتوافق فقط).
- `migration_059_master_reel_queue.sql` — يضيف `master.last_reeled_at` + index على NULL + backfill NOW() لكل المتاجر الموجودة (يمنع flood عند أوّل deploy). **لازم قبل ما يشتغل batch reels.**

**dependencies جديدة في requirements.txt:**
- `imageio==2.34.2` + `imageio-ffmpeg==0.5.1` (~30MB، ffmpeg مدمج في الـwheel، لا يحتاج binary خارجي على Railway).

**/ig landing page**:
- `app/ig/page.tsx` + `app/ig/IgCtaButton.tsx` في مستودع dealpulseksa-web. كل النقرات/النسخات تحمل `details='ig_bio'` في `action_logs` — يعزل ترافيك إنستقرام في تحليلات المتجر. الصفحة `noindex, follow` (canonical للموقع الرئيسي).
