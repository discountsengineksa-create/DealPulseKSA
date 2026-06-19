"""مولّد Reels متعدّد المتاجر — كل 6 متاجر جاهزون → Reel واحد، تلقائياً.

التدفّق:
  1. claim_reel_batch(): SELECT FOR UPDATE SKIP LOCKED لـ6 متاجر بـ
     last_reeled_at=NULL (LIFO: آخر منضافين)؛ نضع NOW() مباشرة لتأمين الـlock.
  2. render_batch_mp4(): يحضّر 6 شرائح 5 ثوان، انتقالات fade، 1080×1920 (9:16
     Reels-spec)، 30fps. كل شريحة = البوستر + اسم المتجر + نسبة الخصم + الكود.
  3. upload_reel_video(): يرفع MP4 على Cloudinary بـresource_type='video'.
  4. build_batch_caption(): caption مجمَّع يذكر كل المتاجر الـ6 + أكوادهم +
     CTA «الرابط في البايو»، مع هاشتاقات SEO شاملة (مثل caption إنستقرام
     لمنشور واحد لكن مع جمع كلمات كل المتاجر).
  5. run_pending_batches(): يكرّر العملية ما دام عدد المنتظرين ≥ 6
     (حد أقصى 3 ريلز/تشغيل واحد — حماية من spam-trigger).

الصوت: غير مدمج افتراضياً. الـMP4 صامت — Instagram يقبل ذلك بدون مشاكل.
لتفعيل موسيقى خلفية: ضع ملف MP3/M4A في `audio/` وضع المسار في env
`REELS_AUDIO_PATH`. الـgenerator يدمجه تلقائياً إذا وُجد.

ملاحظة صريحة: Instagram Graph API لا يعرض الصوتات الترند في السعودية —
هذا قرار من Meta لحماية الملكية الموسيقية. لا يمكن اختيارها برمجياً.
"""
from __future__ import annotations

import io
import os
import time
from typing import Any

import numpy as np
from psycopg2.extras import RealDictCursor


REEL_W, REEL_H = 1080, 1920   # 9:16 Reels-spec
FPS = 30
SECONDS_PER_STORE = 5
FADE_FRAMES = 6                # ~200ms fade بين الشرائح
BATCH_SIZE = 6
MAX_BATCHES_PER_RUN = 3        # حماية: 3 ريلز كحد أقصى في تشغيل واحد


# ════════════════════════════════════════════════════════════════════════
# 1) Claim — atomic lock للـ6 متاجر التالية في القائمة
# ════════════════════════════════════════════════════════════════════════
def claim_reel_batch(conn, size: int = BATCH_SIZE) -> list[dict]:
    """يحجز آخر `size` متاجر منتظرة (LIFO) ويضع last_reeled_at=NOW() فوراً.

    SELECT … FOR UPDATE SKIP LOCKED + UPDATE in WITH = atomic claim. بثّان
    متزامنان لن يستهلكان نفس المجموعة.

    Returns:
        قائمة dicts للمتاجر المحجوزة. فاضية = لا منتظرين أو أقل من size.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            WITH batch AS (
                SELECT id
                FROM master
                WHERE last_reeled_at IS NULL
                  AND (
                      publish_channels IS NULL
                      OR 'instagram' = ANY(
                          string_to_array(COALESCE(publish_channels, ''), ',')
                      )
                  )
                ORDER BY id DESC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            ),
            claim AS (
                UPDATE master m
                SET last_reeled_at = NOW()
                FROM batch
                WHERE m.id = batch.id
                RETURNING m.id, m.store_id, m.name_en, m.public_coupon,
                          m.discount_value, m.extra_offer,
                          m.social_poster_url, m.logo_url, m.affiliate_link,
                          m.store_tags
            )
            SELECT * FROM claim ORDER BY id DESC
            """,
            (size,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    if len(rows) < size:
        # لو طلعت أقل من 6 — نتراجع. سياسة المالك: نظبر للسادس حتى لو شهر.
        conn.rollback()
        return []
    conn.commit()
    return rows


# ════════════════════════════════════════════════════════════════════════
# 2) Render — توليد MP4 من 6 صور
# ════════════════════════════════════════════════════════════════════════
def _fetch_poster_pil(url: str | None):
    """يحمّل رابط الصورة كـPIL.Image. None = نُرجع لوحة سوداء fallback."""
    from PIL import Image
    import requests
    if not url:
        return Image.new("RGB", (REEL_W, REEL_H), (10, 10, 10))
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        return img
    except Exception:
        return Image.new("RGB", (REEL_W, REEL_H), (10, 10, 10))


def _fit_to_reel(img):
    """يقصّ/يحشو الصورة إلى 1080×1920 (9:16) بـcrop يحافظ على نسبة الصورة.
    البوسترات الأصلية 1080×1080 (1:1) — نضعها في الوسط على خلفية متدرّجة."""
    from PIL import Image, ImageFilter
    iw, ih = img.size
    canvas = Image.new("RGB", (REEL_W, REEL_H), (15, 23, 42))

    # خلفية ضبابية من الصورة نفسها (يملأ الجوانب بصرياً)
    bg = img.copy().resize((REEL_W, REEL_H), Image.LANCZOS).filter(
        ImageFilter.GaussianBlur(40)
    )
    canvas.paste(bg, (0, 0))

    # نُحاذي البوستر مركزياً، نُكبّره لأقصى حجم يحفظ النسبة داخل 9:16
    scale = min(REEL_W / iw, (REEL_H - 400) / ih)  # -400 لمساحة النص أعلى/أسفل
    nw, nh = int(iw * scale), int(ih * scale)
    fg = img.resize((nw, nh), Image.LANCZOS)
    x = (REEL_W - nw) // 2
    y = (REEL_H - nh) // 2
    canvas.paste(fg, (x, y))
    return canvas


def _shape_ar(text: str) -> str:
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaper = arabic_reshaper.ArabicReshaper(
            configuration={"delete_harakat": False, "support_ligatures": True}
        )
        return get_display(reshaper.reshape(str(text)))
    except Exception:
        return str(text)


_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FONT = os.path.join(_ROOT, "NotoSansArabic-Bold.ttf")


def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(_FONT, size)
    except Exception:
        return ImageFont.load_default()


def _draw_overlay(img, store: dict):
    """يرسم اسم المتجر + الخصم + الكود فوق الـcanvas. تصميم نظيف بدون تشويش."""
    from PIL import ImageDraw

    draw = ImageDraw.Draw(img, "RGBA")

    # شريط براند علوي
    draw.rectangle([(0, 0), (REEL_W, 130)], fill=(0, 0, 0, 180))
    brand = _shape_ar("نبض الصفقات — كوبونات السعودية")
    f_brand = _font(40)
    bb = draw.textbbox((0, 0), brand, font=f_brand)
    draw.text(((REEL_W - (bb[2] - bb[0])) // 2 - bb[0], 50),
              brand, font=f_brand, fill=(255, 255, 255))

    # كتلة معلومات سفلية: اسم المتجر + نسبة الخصم + كود
    name = (store.get("store_id") or "").strip()
    discount = (store.get("discount_value") or "").strip()
    coupon = (store.get("public_coupon") or "").strip()

    # خلفية شفافة سوداء أسفل لتحسين قراءة النص
    draw.rectangle([(0, REEL_H - 380), (REEL_W, REEL_H)], fill=(0, 0, 0, 200))

    # اسم المتجر بحجم كبير
    name_t = _shape_ar(name)
    f_name = _font(80)
    nb = draw.textbbox((0, 0), name_t, font=f_name)
    draw.text(((REEL_W - (nb[2] - nb[0])) // 2 - nb[0], REEL_H - 350),
              name_t, font=f_name, fill=(255, 255, 255))

    # نسبة الخصم (لو موجودة) بلون زمردي
    if discount:
        disc_t = _shape_ar(f"خصم {discount}")
        f_disc = _font(56)
        db = draw.textbbox((0, 0), disc_t, font=f_disc)
        draw.text(((REEL_W - (db[2] - db[0])) // 2 - db[0], REEL_H - 240),
                  disc_t, font=f_disc, fill=(16, 185, 129))

    # كود الخصم
    if coupon:
        code_t = _shape_ar(f"الكود: {coupon}")
        f_code = _font(48)
        cb = draw.textbbox((0, 0), code_t, font=f_code)
        draw.text(((REEL_W - (cb[2] - cb[0])) // 2 - cb[0], REEL_H - 160),
                  code_t, font=f_code, fill=(255, 255, 255))

    # CTA
    cta = _shape_ar("الرابط في البايو 🔗")
    f_cta = _font(40)
    tb = draw.textbbox((0, 0), cta, font=f_cta)
    draw.text(((REEL_W - (tb[2] - tb[0])) // 2 - tb[0], REEL_H - 85),
              cta, font=f_cta, fill=(255, 220, 0))

    return img


def _render_store_frame(store: dict):
    """يولّد إطار 1080×1920 لمتجر واحد. يُكرَّر FPS × SECONDS_PER_STORE مرة."""
    poster_url = store.get("social_poster_url") or store.get("logo_url")
    img = _fetch_poster_pil(poster_url)
    img = _fit_to_reel(img)
    img = _draw_overlay(img, store)
    return np.asarray(img)


def _crossfade(frame_a, frame_b, t: float):
    """انتقال fade بين إطارين. t=0 → frame_a، t=1 → frame_b. يحفظ uint8."""
    a = frame_a.astype(np.float32)
    b = frame_b.astype(np.float32)
    mix = a * (1 - t) + b * t
    return np.clip(mix, 0, 255).astype(np.uint8)


def render_batch_mp4(stores: list[dict]) -> bytes:
    """يبني فيديو MP4 من قائمة متاجر. كل متجر يظهر SECONDS_PER_STORE ثوان،
    مع انتقال fade خفيف بين كل اثنين متتاليين."""
    import imageio.v2 as imageio

    # ١) ولّد إطاراً واحداً ثابتاً لكل متجر (سيُكرَّر زمنياً)
    base_frames = [_render_store_frame(s) for s in stores]

    out_path = os.path.join(_ROOT, ".tmp_reel.mp4")
    writer = imageio.get_writer(
        out_path, fps=FPS,
        codec="libx264",
        quality=8,                 # 0-10، 8 ≈ visually-lossless مع حجم معقول
        macro_block_size=1,        # يقبل 1080×1920 بدون warnings
        pixelformat="yuv420p",     # متوافق مع IG وكل المشغّلات
    )
    try:
        total_frames_per_store = FPS * SECONDS_PER_STORE
        for idx, frame in enumerate(base_frames):
            # ٢) عرض ثابت للمتجر، مع fade-in في البداية و fade-out في النهاية
            for f in range(total_frames_per_store):
                if f < FADE_FRAMES and idx > 0:
                    # fade من المتجر السابق إلى الحالي
                    t = f / FADE_FRAMES
                    img = _crossfade(base_frames[idx - 1], frame, t)
                else:
                    img = frame
                writer.append_data(img)
    finally:
        writer.close()

    with open(out_path, "rb") as f:
        data = f.read()
    try:
        os.remove(out_path)
    except OSError:
        pass
    return data


# ════════════════════════════════════════════════════════════════════════
# 3) Upload — Cloudinary video
# ════════════════════════════════════════════════════════════════════════
def upload_reel_video(mp4_bytes: bytes, slug: str) -> tuple[str | None, str | None]:
    """يرفع MP4 إلى Cloudinary بـresource_type='video'.

    Returns:
        (secure_url, None) عند النجاح
        (None, error_message) عند الفشل — حتى نسجّل السبب الفعلي في DB.

    تغييرات حاسمة:
    1. نستعمل upload() لا upload_large() — الأخيرة chunked وتتوقّع file path وليس bytes.
       MP4 الخاص بنا ~5MB، upload() الكافي ويقبل file-like object.
    2. نلفّ bytes في BytesIO — Cloudinary Python SDK يتوقّع file-like للفيديو.
    3. نرجع تفاصيل الخطأ بدل None صامت — يصل لـsocial_posts_log.error_message.
    """
    if not os.getenv("CLOUDINARY_CLOUD_NAME"):
        return None, "CLOUDINARY_CLOUD_NAME not set"
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError as e:
        return None, f"cloudinary import: {e}"

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )
    try:
        file_obj = io.BytesIO(mp4_bytes)
        result = cloudinary.uploader.upload(
            file_obj,
            public_id=f"reels/batch_{slug}",
            resource_type="video",
            overwrite=True,
            chunk_size=6_000_000,  # 6MB chunk داخلياً — يكفي لـmp4 الكامل
        )
        url = result.get("secure_url")
        if not url:
            return None, f"cloudinary returned no URL: {result}"
        return url, None
    except Exception as e:
        # نرجع التفاصيل الفعلية: نوع الخطأ + الرسالة + أول 200 حرف لو طويلة
        err = f"{type(e).__name__}: {str(e)[:300]}"
        print(f"[reels_batch] cloudinary video upload failed: {err}")
        return None, err


# ════════════════════════════════════════════════════════════════════════
# 4) Caption — مجمَّع لكل متاجر الـbatch
# ════════════════════════════════════════════════════════════════════════
def build_batch_caption(stores: list[dict]) -> str:
    """caption مجمَّع: hook + قائمة المتاجر + CTA + هاشتاقات SEO شاملة."""
    from api.social.template import _build_hashtags  # type: ignore

    lines = [
        f"🔥 {len(stores)} كوبون حصري في ريل واحد — أحفظ المنشور قبل ينتهي",
        "احفظ 📌 + تابعنا للحصول على أحدث الأكواد يومياً",
        "",
        "🛍️ المتاجر في هذا الريل:",
    ]
    for i, s in enumerate(stores, start=1):
        name = (s.get("store_id") or "").strip()
        disc = (s.get("discount_value") or "").strip()
        code = (s.get("public_coupon") or "").strip()
        bits = [name]
        if disc:
            bits.append(f"خصم {disc}")
        if code:
            bits.append(f"كود: {code}")
        lines.append(f"{i}. " + " — ".join(bits))
    lines.extend([
        "",
        "🔗 الرابط في البايو — اضغطه واختر متجرك واستخدم الكود",
        "💬 علّق باسم المتجر اللي استفدت منه",
        "",
        ".",
        ".",
    ])

    # نجمع هاشتاقات كل المتاجر معاً (مع dedup) — تغطية فئات أوسع لـSEO
    pooled: list[str] = []
    for s in stores:
        pooled.extend(_build_hashtags(s, platform="instagram"))
    # dedup حافظ الترتيب
    seen: set[str] = set()
    uniq: list[str] = []
    for h in pooled:
        k = h.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    # Instagram حد 30 — نأخذ أول 30 بعد الـdedup
    lines.append(" ".join(uniq[:30]))
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════
# 5) Run — نقطة الدخول للـdispatcher
# ════════════════════════════════════════════════════════════════════════
def run_pending_batches(conn) -> int:
    """يُنتج Reels لكل دفعات الـ6 المنتظرة. يُرجع عدد Reels المنشورة بنجاح.

    حد أقصى MAX_BATCHES_PER_RUN ريل/تشغيل واحد (حماية).
    تشغيل لاحق يلتقط أي بقايا (نادراً — البث الواحد يفجّر التشغيل التالي).
    """
    from api.social.platforms.instagram import InstagramPoster
    from api.social.image_specs import platform_image_url
    from api.social.dispatcher import _insert_log, _update_log  # تدوير

    poster = InstagramPoster()
    if not poster.is_configured():
        return 0

    published = 0
    for _ in range(MAX_BATCHES_PER_RUN):
        batch = claim_reel_batch(conn)
        if not batch:
            break  # أقل من 6 منتظرين — نتوقّف

        # سجّل صف log للـReel المجمَّع (نستعمل master_id لأقدم متجر فقط
        # لربط الصف بمفتاح أجنبي صحيح — store_id يحمل أسماء كل الـ6 في details)
        anchor = batch[-1]   # أقدم متجر في الـbatch (LIFO → آخر العنصر)
        log_id = _insert_log(
            conn,
            master_id=anchor["id"],
            store_id=", ".join(s["store_id"] for s in batch),
            platform="instagram_reel_batch",
            post_text=build_batch_caption(batch),
            image_url=anchor.get("social_poster_url"),
        )
        conn.commit()

        try:
            mp4 = render_batch_mp4(batch)
            slug = f"{int(time.time())}_{anchor['id']}"
            video_url, upload_err = upload_reel_video(mp4, slug)
            if not video_url:
                # نلوغ السبب الفعلي بدل رسالة عامة
                _update_log(conn, log_id, status="failed",
                            error_message=f"cloudinary upload: {upload_err}")
                conn.commit()
                _release_batch(conn, [s["id"] for s in batch])
                break

            caption = build_batch_caption(batch)
            cover = platform_image_url(
                anchor.get("social_poster_url") or anchor.get("logo_url"),
                "instagram",
            )
            result = poster.post_reel(caption, video_url, cover_url=cover)
            if result.error:
                _update_log(conn, log_id, status="failed",
                            error_message=result.error)
                conn.commit()
                _release_batch(conn, [s["id"] for s in batch])
                break

            _update_log(conn, log_id, status="sent",
                        platform_post_id=result.platform_post_id or "")
            conn.commit()
            published += 1
        except Exception as e:
            _update_log(conn, log_id, status="failed",
                        error_message=f"{type(e).__name__}: {e}")
            conn.commit()
            _release_batch(conn, [s["id"] for s in batch])
            import traceback
            print(f"[reels_batch] crashed: {traceback.format_exc()}")
            break

    return published


def _release_batch(conn, ids: list[int]) -> None:
    """يعيد المتاجر للقائمة (last_reeled_at=NULL) عند فشل النشر — حماية:
    لا نخسر متاجر في reel فشل، تتاح للتشغيل التالي."""
    if not ids:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE master SET last_reeled_at = NULL WHERE id = ANY(%s)",
            (ids,),
        )
    conn.commit()
