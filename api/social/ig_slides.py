"""مولّد شرائح إضافية للـCarousel على إنستقرام.

الفلسفة:
- Slide 1 = البوستر الأصلي من الستوديو (social_poster_url) — لا نلمسه.
- Slide 2 = «كيف تستخدم الكود؟» — بطاقة تعليمات مولَّدة دقيقة لكل متجر.

نولّد Slide 2 بـPIL باستخدام نفس الخط العربي للستوديو (NotoSansArabic-Bold)،
نرفعه إلى Cloudinary بـpublic_id ثابت لكل متجر (store_slug) — أي إعادة بث
لنفس المتجر تستخدم نفس الرابط (overwrite=True يضمن التحديث لو تغيّر المحتوى).

شروط التشغيل:
- Cloudinary مهيّأ (CLOUDINARY_CLOUD_NAME + API_KEY + API_SECRET في env).
- الخط NotoSansArabic-Bold.ttf موجود في جذر المستودع (نفس الستوديو).
- arabic_reshaper + python-bidi مثبَّتان (موجودان في requirements.txt).

لو أحد الشروط مفقود — يُرجع None، الـdispatcher يقع على single-image تلقائياً.
"""
from __future__ import annotations

import io
import os
import re
from typing import Optional

# نستورد الـheavy deps داخل الدوال — يحمي الاستيراد العام من ImportError
# لو البيئة منقوصة (مثلاً اختبارات بدون pillow).


# جذر المستودع — حيث NotoSansArabic-Bold.ttf
_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FONT_AR = os.path.join(_ROOT_DIR, "NotoSansArabic-Bold.ttf")

# ─── لوحة ألوان مطابقة لستوديو الداشبورد (هوية موحّدة) ───────────────────
_BG_TOP     = (250, 250, 248)   # cream
_BG_BOTTOM  = (232, 240, 234)   # mint-cream
_EMERALD    = (16, 185, 129)
_INK        = (31, 41, 55)
_INK_SOFT   = (107, 114, 128)
_WHITE      = (255, 255, 255)
_CANVAS     = 1080


def _slug_for(store_id: str) -> str:
    """يولّد slug آمن للاستخدام كـpublic_id في Cloudinary من اسم المتجر العربي."""
    s = (store_id or "store").strip()
    # نُحوّل ما ليس [حرف/رقم] إلى _ ، نضغط الـ_ المتكرّرة، ونقصّ الأطراف.
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE).strip("_")
    return s[:80] or "store"


def _shape_ar(text: str) -> str:
    """تشكيل + bidi لنص عربي قبل التمرير لـPIL (يمنع قلب/كسر الحروف)."""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaper = arabic_reshaper.ArabicReshaper(configuration={
            "delete_harakat": False, "support_ligatures": True,
        })
        return get_display(reshaper.reshape(str(text)))
    except Exception:
        return str(text)


def _font(size: int):
    """يُرجع FreeTypeFont بحجم محدّد، أو الخط الافتراضي لو الملف مفقود."""
    from PIL import ImageFont
    try:
        return ImageFont.truetype(_FONT_AR, size)
    except Exception:
        return ImageFont.load_default()


def _draw_gradient_bg(img):
    """خلفية متدرّجة عمودية cream→mint — نفس مزاج الستوديو."""
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    for y in range(_CANVAS):
        ratio = y / _CANVAS
        r = int(_BG_TOP[0] + (_BG_BOTTOM[0] - _BG_TOP[0]) * ratio)
        g = int(_BG_TOP[1] + (_BG_BOTTOM[1] - _BG_TOP[1]) * ratio)
        b = int(_BG_TOP[2] + (_BG_BOTTOM[2] - _BG_TOP[2]) * ratio)
        draw.line([(0, y), (_CANVAS, y)], fill=(r, g, b))


def _center_x(draw, text: str, font) -> int:
    """يحسب إزاحة x لتوسيط النص أفقياً على الـCanvas."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return (_CANVAS - (bbox[2] - bbox[0])) // 2 - bbox[0]


def render_howto_slide(store_name: str, coupon: str | None) -> Optional[bytes]:
    """يولّد شريحة «كيف تستخدم الكود؟» 1080×1080 PNG كـbytes.

    Args:
        store_name: اسم المتجر بالعربي (يظهر في الترويسة).
        coupon: كود الخصم إن وُجد (يُذكر في الخطوة 3 بشكل بارز).

    Returns:
        bytes للصورة PNG، أو None لو PIL/الخط مفقود.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return None

    img = Image.new("RGB", (_CANVAS, _CANVAS), _BG_TOP)
    _draw_gradient_bg(img)
    draw = ImageDraw.Draw(img)

    # ── ترويسة: «كيف تستخدم الكود؟» ────────────────────────────────
    title = _shape_ar("كيف تستخدم الكود؟")
    f_title = _font(72)
    draw.text((_center_x(draw, title, f_title), 100), title, font=f_title, fill=_INK)

    # خط فاصل تحت الترويسة (هامش كافٍ تحت الـdescenders)
    draw.rectangle([(_CANVAS // 2 - 80, 240), (_CANVAS // 2 + 80, 248)], fill=_EMERALD)

    # ── اسم المتجر ────────────────────────────────────────────────
    name = _shape_ar(store_name)
    f_name = _font(48)
    draw.text((_center_x(draw, name, f_name), 280), name, font=f_name, fill=_EMERALD)

    # ── الخطوات الأربع ────────────────────────────────────────────
    steps = [
        ("١", "اضغط الرابط في البايو"),
        ("٢", "اختر المتجر من القائمة"),
        ("٣", f"انسخ كود الخصم: {coupon}" if coupon else "انسخ كود الخصم"),
        ("٤", "ألصق الكود عند إتمام الشراء"),
    ]

    f_num  = _font(56)
    f_step = _font(42)
    y0 = 420
    row_h = 125
    for i, (num, text) in enumerate(steps):
        y = y0 + i * row_h
        # دائرة الرقم على اليمين (RTL)
        cx = _CANVAS - 130
        cy = y + 35
        draw.ellipse([(cx - 45, cy - 45), (cx + 45, cy + 45)], fill=_EMERALD)
        num_shape = _shape_ar(num)
        nb = draw.textbbox((0, 0), num_shape, font=f_num)
        draw.text((cx - (nb[2] - nb[0]) // 2 - nb[0], cy - (nb[3] - nb[1]) // 2 - nb[1]),
                  num_shape, font=f_num, fill=_WHITE)
        # نص الخطوة على اليسار من الدائرة
        step_shape = _shape_ar(text)
        sb = draw.textbbox((0, 0), step_shape, font=f_step)
        step_w = sb[2] - sb[0]
        # محاذاة اليمين (يبدأ النص من قرب الدائرة باتجاه اليسار)
        x_text = cx - 90 - step_w - sb[0]
        draw.text((x_text, y + 15), step_shape, font=f_step, fill=_INK)

    # ── Footer: العلامة ─────────────────────────────────────────────
    footer = _shape_ar("نبض الصفقات — كوبونات السعودية يومياً")
    f_foot = _font(34)
    draw.text((_center_x(draw, footer, f_foot), _CANVAS - 90),
              footer, font=f_foot, fill=_INK_SOFT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def upload_howto_slide(store_id: str, store_name: str, coupon: str | None) -> str | None:
    """يولّد شريحة الـHow-To ويرفعها إلى Cloudinary. يُرجع secure_url أو None.

    public_id ثابت لكل متجر — إعادة البث تُحدّث نفس الرابط (لا تتراكم نُسخ).
    """
    if not os.getenv("CLOUDINARY_CLOUD_NAME"):
        return None
    try:
        import cloudinary
        import cloudinary.uploader
    except ImportError:
        return None

    img_bytes = render_howto_slide(store_name, coupon)
    if not img_bytes:
        return None

    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    )

    slug = _slug_for(store_id)
    try:
        result = cloudinary.uploader.upload(
            img_bytes,
            public_id=f"store_posters/{slug}_howto",
            overwrite=True,
            resource_type="image",
            format="jpg",  # JPEG مقبول عند Meta — WebP مرفوض
        )
        return result.get("secure_url")
    except Exception as e:
        print(f"[ig_slides] cloudinary upload failed for {store_id}: {e}")
        return None
