"""مولّد كاروسيلات المحتوى — قالب «Dark Luxe» فاخر بهوية نبض الصفقات.

محتوى نمو (نصائح/أنواع/خطوات) بمستوى شركات: خلفية زمردية-فحمية متدرّجة،
اللوقو الرسمي، حاويات بحواف ناعمة وظلال، خط Cairo العصري، ولمسات زمردية.
يحوّل كل «مفهوم» (kicker + خطّاف + نقاط + CTA) إلى مجموعة شرائح 1080×1350 (4:5).

يعيد استخدام تشكيل العربي من ig_slides. الشروط: Pillow + arabic_reshaper +
python-bidi + Cairo-Bold.ttf + logo2.png (في جذر المستودع). لو ناقص شي → [].
"""
from __future__ import annotations

import io
import os
from typing import TypedDict

from api.social.ig_slides import _shape_ar  # تشكيل عربي موحّد (reuse)

# ─── أصول ─────────────────────────────────────────────────────────────────
_ROOT      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Cairo-Bold بالمستودع لاتيني فقط (لا يدعم العربي) → نستخدم Noto للعربي.
_FONT_PATH = os.path.join(_ROOT, "NotoSansArabic-Bold.ttf")
_LOGO_NIGHT = os.path.join(_ROOT, "logo_for_watermark.png")  # شفّاف، لوقو فاتح
_LOGO_DAY   = os.path.join(_ROOT, "logo2.png")

# ─── أبعاد ولوحة ألوان فاخرة ───────────────────────────────────────────────
W, H   = 1080, 1350
MARGIN = 96

BG_TOP    = (9, 33, 27)      # أخضر-فحمي عميق
BG_BOTTOM = (4, 16, 12)      # شبه أسود
EMERALD       = (16, 185, 129)
EMERALD_BRIGHT = (52, 211, 153)
EMERALD_DEEP   = (6, 78, 59)
WHITE   = (255, 255, 255)
MUTED   = (148, 173, 162)
CARD    = (17, 45, 37)
INK_ON_EMERALD = (5, 26, 20)

_AR_NUMS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


class ContentConcept(TypedDict, total=False):
    kicker: str         # تصنيف صغير أعلى الغلاف (اختياري)
    title: str          # خطّاف الغلاف
    points: list[str]   # نقطة لكل شريحة
    cta: str            # نداء أخير


# ─── بدائيات ───────────────────────────────────────────────────────────────
def _font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _canvas():
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (*BG_BOTTOM, 255))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(
            int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t),
            int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t),
            int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t), 255))
    # توهّج زمردي خفيف أعلى يمين (لمسة عمق)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 520, -360, W + 360, 320], fill=(*EMERALD, 38))
    from PIL import ImageFilter
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(180)))
    return img


def _cx(draw, shaped: str, font) -> int:
    bb = draw.textbbox((0, 0), shaped, font=font)
    return (W - (bb[2] - bb[0])) // 2 - bb[0]


def _wrap(draw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if draw.textbbox((0, 0), _shape_ar(cand), font=font)[2] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_lines(draw, lines, font, y0, fill, lh) -> int:
    y = y0
    for ln in lines:
        s = _shape_ar(ln)
        draw.text((_cx(draw, s, font), y), s, font=font, fill=fill)
        y += lh
    return y


def _logo(img, target_w: int, top_y: int) -> None:
    from PIL import Image
    path = _LOGO_NIGHT if os.path.exists(_LOGO_NIGHT) else _LOGO_DAY
    if not os.path.exists(path):
        return
    logo = Image.open(path).convert("RGBA")
    h = int(logo.height * target_w / logo.width)
    img.alpha_composite(logo.resize((target_w, h), Image.LANCZOS), ((W - target_w) // 2, top_y))


def _card(img, box, radius: int, fill) -> None:
    from PIL import Image, ImageDraw, ImageFilter
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([x0, y0 + 20, x1, y1 + 20], radius=radius, fill=(0, 0, 0, 120))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(34)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=(*fill, 240))
    d.rounded_rectangle(box, radius=radius, outline=(*EMERALD_DEEP, 255), width=2)


def _footer(draw) -> None:
    draw.line([(MARGIN, H - 158), (W - MARGIN, H - 158)], fill=(*EMERALD_DEEP, 255), width=2)
    fh = _font(40)
    hs = _shape_ar("@dealpulseksa")
    draw.text((_cx(draw, hs, fh), H - 128), hs, font=fh, fill=EMERALD_BRIGHT)
    fm = _font(30)
    ms = _shape_ar("كوبونات وأكواد خصم السعودية يومياً")
    draw.text((_cx(draw, ms, fm), H - 76), ms, font=fm, fill=MUTED)


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ─── شرائح ─────────────────────────────────────────────────────────────────
def _render_cover(concept: ContentConcept) -> bytes:
    from PIL import ImageDraw
    img = _canvas()
    _logo(img, 168, 110)
    draw = ImageDraw.Draw(img)
    kicker = concept.get("kicker") or "نبض الصفقات"
    fk = _font(38)
    ks = _shape_ar(kicker.upper() if kicker.isascii() else kicker)
    draw.text((_cx(draw, ks, fk), 330), ks, font=fk, fill=EMERALD_BRIGHT)
    fh = _font(82)
    lines = _wrap(draw, concept["title"], fh, W - 2 * MARGIN)
    lh, block = 108, len(_wrap(draw, concept["title"], fh, W - 2 * MARGIN)) * 108
    y0 = (H - block) // 2 + 10
    y1 = _draw_lines(draw, lines, fh, y0, WHITE, lh)
    draw.rounded_rectangle([W // 2 - 74, y1 + 30, W // 2 + 74, y1 + 44], radius=7, fill=EMERALD)
    _footer(draw)
    return _png(img)


def _render_point(num: int, text: str) -> bytes:
    from PIL import ImageDraw
    img = _canvas()
    _logo(img, 118, 96)
    draw = ImageDraw.Draw(img)
    card = [MARGIN - 16, 430, W - MARGIN + 16, 980]
    _card(img, card, 52, CARD)
    draw = ImageDraw.Draw(img)
    cx, cy = W // 2, card[1] + 110
    draw.ellipse([cx - 64, cy - 64, cx + 64, cy + 64], fill=EMERALD)
    fn = _font(66)
    nb = _shape_ar(str(num).translate(_AR_NUMS))
    bb = draw.textbbox((0, 0), nb, font=fn)
    draw.text((cx - (bb[2] - bb[0]) // 2 - bb[0], cy - (bb[3] - bb[1]) // 2 - bb[1]),
              nb, font=fn, fill=INK_ON_EMERALD)
    ft = _font(58)
    lines = _wrap(draw, text, ft, W - 2 * MARGIN - 60)
    _draw_lines(draw, lines, ft, card[1] + 250, WHITE, 80)
    _footer(draw)
    return _png(img)


def _render_cta(cta: str) -> bytes:
    from PIL import ImageDraw
    img = _canvas()
    _logo(img, 190, 150)
    draw = ImageDraw.Draw(img)
    ft = _font(64)
    lines = _wrap(draw, cta, ft, W - 2 * MARGIN)
    block = len(lines) * 92
    y0 = (H - block) // 2 - 30
    y1 = _draw_lines(draw, lines, ft, y0, WHITE, 92)
    # زر «تابعنا» بهيئة pill زمردية
    label = _shape_ar("تابعنا  @dealpulseksa")
    fp = _font(44)
    pb = draw.textbbox((0, 0), label, font=fp)
    pw, ph = pb[2] - pb[0], pb[3] - pb[1]
    px0 = (W - pw) // 2 - 56
    py0 = y1 + 56
    draw.rounded_rectangle([px0, py0, px0 + pw + 112, py0 + ph + 56], radius=(ph + 56) // 2, fill=EMERALD)
    draw.text(((W - pw) // 2 - pb[0], py0 + 28 - pb[1]), label, font=fp, fill=INK_ON_EMERALD)
    _footer(draw)
    return _png(img)


# ─── الواجهة العامة ────────────────────────────────────────────────────────
def render_content_slides(concept: ContentConcept) -> list[bytes]:
    """يولّد شرائح PNG (غلاف + نقطة لكل عنصر + CTA) لمفهوم محتوى واحد.
    يُرجع [] لو PIL/الخط مفقود."""
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return []
    slides = [_render_cover(concept)]
    for i, pt in enumerate(concept.get("points", []), start=1):
        slides.append(_render_point(i, pt))
    if concept.get("cta"):
        slides.append(_render_cta(concept["cta"]))
    return slides
