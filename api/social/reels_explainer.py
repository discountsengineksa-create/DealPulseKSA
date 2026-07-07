"""مولّد فيديو شرح (Explainer) للموقع/البوت — مشاهد متتابعة موقّتة بهوية Dark Luxe.

الاتفاق: البنت تسجّل صوتها فوق الفيديو فقط. الفيديو يوري بصرياً كل نقطة يذكرها
السكربت: الخطّاف → فكرة «كل الأكواد بمكان واحد» → موك-أب جوال (اختَر/انسخ/الصق/
السعر ينزل) → الأقسام → المفضّلة → شات بوت تيليجرام → مجاني + الرابط بالبايو.

النصوص على الشاشة (captions) = عناوين مختصرة تعمل كترجمة (subtitles) تقرأ عليها
البنت السكربت الكامل بإيقاعها. لا أسماء براندات (احتراماً لشروط الأفلييت).

التقنية: يعيد استخدام أدوات reels_render (Dark Luxe) + مشاهد جديدة → ffmpeg H.264.
تشغيل:
    python -m api.social.reels_explainer --script 1 --out out_explainer
    python -m api.social.reels_explainer --all --out out_explainer
"""
from __future__ import annotations

import math
import os
import subprocess
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter

from api.social.ig_slides import _shape_ar
from api.social.reels_render import (
    W, H, FPS, _base_background, _text_sprite, _paste_center, _font,
    _particles, _draw_particles, _rounded, _logo_sprite,
    ease_out_cubic, ease_out_back, ease_in_out, seg, clamp01,
    EMERALD, EMERALD_BRIGHT, EMERALD_DEEP, GOLD, GOLD_BRIGHT,
    WHITE, MUTED, INK, CHIP, _AR_NUMS,
)

# ─── بدائل سريعة (تُظلّل مستوردات reels_render الثقيلة) ──────────────────────
def _rounded(img, box, radius, fill, outline=None, ow=2, shadow=False):
    """مستطيل دائري بلا ظل full-canvas — أسرع بمراحل من نسخة reels_render."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill)
    if outline:
        d.rounded_rectangle(box, radius=radius, outline=outline, width=ow)


def _draw_particles(img, parts, t):
    """جزيئات مرسومة مباشرة بلا GaussianBlur (كان يبلور كامل الكانفس/فريم)."""
    d = ImageDraw.Draw(img)
    for p in parts:
        y = (p["y"] - p["spd"] * t) % H
        x = p["x"] + math.sin(t * 1.15 + p["ph"]) * p["amp"]
        a = max(18, min(130, int(70 + 55 * math.sin(t * 2.1 + p["ph"]))))
        col = GOLD_BRIGHT if p["gold"] else EMERALD_BRIGHT
        r = p["r"]
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*col, a))


# ─── نصوص متعدّدة الأسطر ─────────────────────────────────────────────────────
_PROBE = ImageDraw.Draw(Image.new("RGBA", (1, 1)))


def _wrap(text: str, font, max_w: int) -> list[str]:
    words, lines, cur = str(text).split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if _PROBE.textbbox((0, 0), _shape_ar(cand), font=font)[2] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def _multiline_sprite(text: str, font, fill, max_w: int, glow=None) -> Image.Image:
    lines = _wrap(text, font, max_w)
    lh = int(font.size * 1.42)
    shaped = [_shape_ar(ln) for ln in lines]
    widths = [_PROBE.textbbox((0, 0), s, font=font)[2] - _PROBE.textbbox((0, 0), s, font=font)[0]
              for s in shaped]
    pad = 46
    ws = max(widths) + pad * 2
    hs = lh * len(lines) + pad * 2
    s = Image.new("RGBA", (ws, hs), (0, 0, 0, 0))
    sd = ImageDraw.Draw(s)
    y = pad
    for sh, wd in zip(shaped, widths):
        bb = sd.textbbox((0, 0), sh, font=font)
        x = (ws - wd) // 2 - bb[0]
        if glow:
            gl = Image.new("RGBA", s.size, (0, 0, 0, 0))
            ImageDraw.Draw(gl).text((x, y - bb[1]), sh, font=font, fill=(*glow, 255))
            s.alpha_composite(gl.filter(ImageFilter.GaussianBlur(14)))
        sd.text((x, y - bb[1]), sh, font=font, fill=fill)
        y += lh
    return s


# ─── ثوابت واجهة ثابتة ──────────────────────────────────────────────────────
def _chrome(img: Image.Image, parts, t_abs: float) -> None:
    """عناصر ثابتة: جزيئات + لوقو صغير أعلى + فوتر."""
    _draw_particles(img, parts, t_abs)
    logo = _logo_sprite()
    if logo is not None:
        lw = 168
        lg = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
        img.alpha_composite(lg, ((W - lw) // 2, 96))
    fs = _text_sprite("@dealpulseksa  ·  نبض الصفقات", _font(34), MUTED)
    img.alpha_composite(fs, ((W - fs.width) // 2, H - 92))


def _caption(img: Image.Image, sprite: Image.Image, tl: float, dur: float) -> None:
    """ترجمة سفلية مع لوح داكن ناعم + تلاشٍ دخول/خروج."""
    a = ease_out_cubic(seg(tl, 0.0, 0.5))
    if dur - tl < 0.5:
        a *= clamp01((dur - tl) / 0.5)
    if a <= 0.02:
        return
    cy = 1600
    pad_x, pad_y = 46, 30
    box = ((W - sprite.width) // 2 - pad_x, cy - pad_y,
           (W + sprite.width) // 2 + pad_x, cy + sprite.height + pad_y)
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _rounded(panel, box, 34, (5, 20, 15, 205), outline=(*EMERALD_DEEP, 180), ow=2, shadow=False)
    sp = sprite
    if a < 0.99:
        panel.putalpha(panel.split()[3].point(lambda p: int(p * a)))
        sp = sprite.copy(); sp.putalpha(sp.split()[3].point(lambda p: int(p * a)))
    img.alpha_composite(panel)
    img.alpha_composite(sp, ((W - sprite.width) // 2, cy))


# ─── موك-أب جوال (المشهد المحوري: كيف يشتغل) ────────────────────────────────
def _ar(n: int) -> str:
    return str(n).translate(_AR_NUMS)


def _scene_phone(img, tl, dur):
    pw, ph = 560, 1010
    px, py = (W - pw) // 2, 360
    _rounded(img, (px, py, px + pw, py + ph), 62, (11, 28, 22, 255), outline=(*EMERALD_DEEP, 255), ow=4)
    sx0, sy0, sx1, sy1 = px + 24, py + 34, px + pw - 24, py + ph - 34
    _rounded(img, (sx0, sy0, sx1, sy1), 46, (6, 18, 14, 255), shadow=False)
    # نقطة السمّاعة
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((W // 2 - 46, py + 16, W // 2 + 46, py + 26), radius=5, fill=(4, 14, 10, 255))

    inner_w = sx1 - sx0 - 80
    cxL, cxR = sx0 + 40, sx1 - 40

    def fade_layer(draw_fn, a, dy=0.0):
        if a <= 0.02:
            return
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(lay), lay)
        if dy:
            lay = ImageChops_offset(lay, 0, int(dy))
        if a < 0.99:
            lay.putalpha(lay.split()[3].point(lambda p: int(p * a)))
        img.alpha_composite(lay)

    # 1) كارت متجر ينزلق (0.2→1.4)
    a1 = ease_out_cubic(seg(tl, 0.2, 1.4))
    cy = sy0 + 60
    def _card(dr, lay):
        dr.rounded_rectangle((cxL, cy, cxR, cy + 150), radius=28, fill=(*CHIP, 255), outline=(*EMERALD_DEEP, 255), width=2)
        dr.ellipse((cxL + 24, cy + 33, cxL + 108, cy + 117), fill=(*EMERALD_DEEP, 255))
        dr.rounded_rectangle((cxL + 132, cy + 46, cxR - 40, cy + 74), radius=8, fill=(*MUTED, 200))
        dr.rounded_rectangle((cxL + 132, cy + 92, cxR - 130, cy + 112), radius=7, fill=(*EMERALD_DEEP, 255))
    fade_layer(_card, a1, dy=(1 - a1) * 40)

    # 2) شريحة الكود + توست «نسخ ✓» (1.6→2.8)
    a2 = ease_out_cubic(seg(tl, 1.6, 2.6))
    ky = cy + 210
    def _code(dr, lay):
        dr.rounded_rectangle((cxL, ky, cxR, ky + 130), radius=26, fill=(10, 26, 21, 255), outline=(*GOLD, 255), width=3)
        lab = _text_sprite("كود الخصم", _font(30), EMERALD_BRIGHT)
        lay.alpha_composite(lab, ((W - lab.width) // 2, ky + 16))
        cod = _text_sprite("DP20", _font(60), GOLD_BRIGHT)
        lay.alpha_composite(cod, ((W - cod.width) // 2, ky + 52))
    fade_layer(_code, a2)
    # توست نسخ
    at = seg(tl, 2.6, 3.2) * (1 - seg(tl, 3.8, 4.4))
    if at > 0.02:
        toast = _text_sprite("تم النسخ", _font(34), INK)
        tw = toast.width + 110
        tx = (W - tw) // 2
        ty = ky + 150
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _rounded(lay, (tx, ty, tx + tw, ty + 66), 33, (*EMERALD_BRIGHT, 255), shadow=False)
        lay.alpha_composite(toast, (tx + 30, ty + 14))
        # علامة صح مرسومة (بدل الإيموجي)
        dl = ImageDraw.Draw(lay)
        chx, chy = tx + tw - 58, ty + 33
        dl.line([(chx, chy), (chx + 12, chy + 14), (chx + 34, chy - 16)], fill=INK, width=6, joint="curve")
        lay.putalpha(lay.split()[3].point(lambda p: int(p * clamp01(at))))
        img.alpha_composite(lay)

    # 3) السعر: قديم يُشطب → جديد أقل ينبض (3.6→5.6)
    py0 = ky + 240
    a_old = ease_out_cubic(seg(tl, 3.4, 4.0))
    if a_old > 0.02:
        old = _text_sprite(f"{_ar(250)} ر.س", _font(58), MUTED)
        _paste_center(img, old, py0, 1.0, a_old)
        strike = seg(tl, 4.2, 4.8)
        if strike > 0:
            d2 = ImageDraw.Draw(img)
            ow = int(old.width * strike)
            d2.line([(W // 2 - old.width // 2, py0), (W // 2 - old.width // 2 + ow, py0)],
                    fill=(*EMERALD_BRIGHT, 255), width=6)
    a_new = seg(tl, 4.8, 5.4)
    if a_new > 0.02:
        beat = 1 + 0.05 * math.sin(max(0, tl - 5.4) * 5)
        new = _text_sprite(f"{_ar(200)} ر.س", _font(88), EMERALD_BRIGHT, glow=EMERALD_DEEP)
        _paste_center(img, new, py0 + 96, (0.7 + ease_out_back(a_new) * 0.3) * beat, ease_out_cubic(a_new))


def ImageChops_offset(im: Image.Image, dx: int, dy: int) -> Image.Image:
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(im, (dx, dy))
    return out


# ─── مشهد الأقسام ────────────────────────────────────────────────────────────
def _scene_categories(img, tl, dur):
    cats = ["أزياء", "أكل وتوصيل", "إلكترونيات", "عطور", "مستلزمات أطفال"]
    cy = 640
    rows = [cats[:2], cats[2:4], cats[4:]]
    d = ImageDraw.Draw(img)
    idx = 0
    for r, row in enumerate(rows):
        sprites = [_text_sprite(c, _font(52), WHITE) for c in row]
        gap = 40
        widths = [sp.width + 96 for sp in sprites]
        total = sum(widths) + gap * (len(row) - 1)
        x = (W - total) // 2
        ry = cy + r * 170
        for sp, cw in zip(sprites, widths):
            a = ease_out_back(seg(tl, 0.3 + idx * 0.22, 1.1 + idx * 0.22))
            idx += 1
            if a > 0.02:
                lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                _rounded(lay, (x, ry, x + cw, ry + 108), 54, (*CHIP, 255), outline=(*EMERALD, 255), ow=2, shadow=True)
                lay.alpha_composite(sp, (x + (cw - sp.width) // 2, ry + (108 - sp.height) // 2))
                sc = min(1.0, a)
                if sc < 0.99:
                    lay.putalpha(lay.split()[3].point(lambda p: int(p * clamp01(a))))
                img.alpha_composite(lay)
            x += cw + gap


# ─── مشهد المفضّلة ───────────────────────────────────────────────────────────
def _scene_favorites(img, tl, dur):
    cx, cy = W // 2, 760
    a = ease_out_back(seg(tl, 0.3, 1.2))
    if a > 0.02:
        # قلب زمردي (مضلّع بسيط) ينبض
        beat = 1 + 0.08 * math.sin(max(0, tl - 1.2) * 4)
        r = int(150 * min(1, a) * beat)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        dl.ellipse((cx - r, cy - r, cx, cy), fill=(*EMERALD_BRIGHT, 255))
        dl.ellipse((cx, cy - r, cx + r, cy), fill=(*EMERALD_BRIGHT, 255))
        dl.polygon([(cx - r, cy - r // 3), (cx + r, cy - r // 3), (cx, cy + r)], fill=(*EMERALD_BRIGHT, 255))
        lay = lay.filter(ImageFilter.GaussianBlur(0.5))
        img.alpha_composite(lay)
    # صف متاجر محفوظة
    a2 = ease_out_cubic(seg(tl, 1.4, 2.2))
    if a2 > 0.02:
        n = 3
        bw, gap = 150, 44
        total = n * bw + (n - 1) * gap
        x = (W - total) // 2
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for i in range(n):
            _rounded(lay, (x, 1000, x + bw, 1150), 28, (*CHIP, 255), outline=(*EMERALD_DEEP, 255), ow=2, shadow=False)
            dl = ImageDraw.Draw(lay)
            dl.ellipse((x + 40, 1035, x + bw - 40, 1075 + 30), fill=(*EMERALD_DEEP, 255))
            x += bw + gap
        lay.putalpha(lay.split()[3].point(lambda p: int(p * a2)))
        img.alpha_composite(lay)


# ─── مشهد بوت تيليجرام ──────────────────────────────────────────────────────
def _bubble(img, side, sprite, y, a, emerald=False):
    pad = 34
    bw = sprite.width + pad * 2
    bh = sprite.height + pad * 2
    m = 90
    if side == "right":
        x1 = W - m; x0 = x1 - bw
        fill = (30, 44, 40, 255)
    else:
        x0 = m; x1 = x0 + bw
        fill = (*EMERALD_DEEP, 255) if emerald else (24, 40, 34, 255)
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _rounded(lay, (x0, y, x1, y + bh), 30, fill, shadow=True)
    lay.alpha_composite(sprite, (x0 + pad, y + pad))
    if a < 0.99:
        lay.putalpha(lay.split()[3].point(lambda p: int(p * a)))
    img.alpha_composite(lay)
    return y + bh


def _scene_bot(img, tl, dur):
    # هيدر بوت
    d = ImageDraw.Draw(img)
    hy = 440
    _rounded(img, (80, hy, W - 80, hy + 120), 30, (14, 34, 28, 255), outline=(*EMERALD_DEEP, 255), ow=2, shadow=False)
    d.ellipse((W - 80 - 96, hy + 16, W - 80 - 16, hy + 96), fill=(*EMERALD, 255))
    name = _text_sprite("بوت نبض الصفقات", _font(40), WHITE)
    img.alpha_composite(name, (W - 80 - 120 - name.width, hy + 38))
    on = _text_sprite("متصل", _font(28), EMERALD_BRIGHT)
    img.alpha_composite(on, (120 + 30, hy + 46))
    d.ellipse((120, hy + 54, 120 + 20, hy + 74), fill=(*EMERALD_BRIGHT, 255))  # نقطة «متصل»

    # فقاعة المستخدم (يمين)
    a1 = ease_out_cubic(seg(tl, 0.4, 1.1))
    u = _text_sprite("أبغى كود خصم المتجر", _font(40), WHITE)
    y = 640
    if a1 > 0.02:
        _bubble(img, "right", u, y, a1)

    # نقاط الكتابة ثم رد البوت (يسار)
    a2 = ease_out_cubic(seg(tl, 1.8, 2.6))
    if a2 > 0.02:
        rep = _text_sprite("تفضّل، كودك جاهز", _font(40), WHITE)
        yb = _bubble(img, "left", rep, y + 190, a2, emerald=True)
        # شريحة كود داخل رد
        a3 = ease_out_back(seg(tl, 2.6, 3.4))
        if a3 > 0.02:
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            cw = 320
            _rounded(lay, (90, yb + 24, 90 + cw, yb + 24 + 110), 24, (10, 26, 21, 255), outline=(*GOLD, 255), ow=3, shadow=True)
            cod = _text_sprite("DP20", _font(58), GOLD_BRIGHT)
            lay.alpha_composite(cod, (90 + (cw - cod.width) // 2, yb + 24 + 26))
            lay.putalpha(lay.split()[3].point(lambda p: int(p * clamp01(a3))))
            img.alpha_composite(lay)


# ─── مشاهد نصية (خطّاف / فكرة / نداء) ───────────────────────────────────────
def _scene_hook(img, tl, dur):
    a = ease_out_back(seg(tl, 0.1, 1.0))
    if a <= 0.02:
        return
    sc = min(1.0, a)
    cx, cy = W // 2, 720
    R = int(130 * (0.6 + sc * 0.4))
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    dl.ellipse((cx - R, cy - R, cx + R, cy + R), fill=(*EMERALD_DEEP, 90))
    dl.ellipse((cx - R, cy - R, cx + R, cy + R), outline=(*EMERALD_BRIGHT, 255), width=18)
    hx0, hy0 = cx + int(R * 0.72), cy + int(R * 0.72)
    dl.line((hx0, hy0, hx0 + int(R * 0.7), hy0 + int(R * 0.7)), fill=(*EMERALD_BRIGHT, 255), width=26)
    if sc < 0.99:
        lay.putalpha(lay.split()[3].point(lambda p: int(p * ease_out_cubic(sc))))
    img.alpha_composite(lay)


def _scene_concept(img, tl, dur):
    # شبكة بلاطات متوهّجة (بلا أسماء براندات)
    cols, rows = 3, 3
    bw, bh, gap = 210, 150, 40
    tw = cols * bw + (cols - 1) * gap
    th = rows * bh + (rows - 1) * gap
    x0 = (W - tw) // 2
    y0 = 560
    i = 0
    for r in range(rows):
        for c in range(cols):
            a = ease_out_back(seg(tl, 0.2 + i * 0.09, 0.9 + i * 0.09))
            i += 1
            if a <= 0.02:
                continue
            x = x0 + c * (bw + gap)
            y = y0 + r * (bh + gap)
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            _rounded(lay, (x, y, x + bw, y + bh), 26, (*CHIP, 255), outline=(*EMERALD_DEEP, 255), ow=2, shadow=True)
            dl = ImageDraw.Draw(lay)
            dl.ellipse((x + bw // 2 - 34, y + bh // 2 - 46, x + bw // 2 + 34, y + bh // 2 + 22), fill=(*EMERALD_DEEP, 255))
            dl.rounded_rectangle((x + 40, y + bh - 44, x + bw - 40, y + bh - 28), radius=8, fill=(*EMERALD, 200))
            lay.putalpha(lay.split()[3].point(lambda p: int(p * clamp01(a))))
            img.alpha_composite(lay)


def _scene_cta(img, tl, dur):
    a = ease_out_back(seg(tl, 0.2, 1.1))
    free = _text_sprite("مجاني بالكامل", _font(74), EMERALD_BRIGHT, glow=EMERALD_DEEP)
    _paste_center(img, free, 720, 0.7 + min(1, a) * 0.3, ease_out_cubic(min(1, a)))
    p = seg(tl, 1.0, 1.7)
    if p > 0.02:
        beat = 1 + 0.04 * math.sin(max(0, tl - 1.7) * 4)
        spr = _text_sprite("الرابط في البايو", _font(58), INK)
        scale = (0.8 + ease_out_back(p) * 0.2) * beat
        w = int(spr.width * scale); h = int(spr.height * scale)
        px0 = (W - w) // 2 - 64; py0 = 900
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _rounded(lay, (px0, py0, px0 + w + 128, py0 + h + 48), (h + 48) // 2, (*EMERALD, 255))
        lay.alpha_composite(spr.resize((w, h), Image.LANCZOS), (px0 + 64, py0 + 24))
        lay.putalpha(lay.split()[3].point(lambda p2: int(p2 * ease_out_cubic(p))))
        img.alpha_composite(lay)


SCENES = {
    "hook": _scene_hook, "concept": _scene_concept, "phone": _scene_phone,
    "categories": _scene_categories, "favorites": _scene_favorites,
    "bot": _scene_bot, "cta": _scene_cta,
}

# ─── سكربتات (نفس المشاهد، صياغة caption مختلفة) ─────────────────────────────
_CAPTIONS = {
    "1": ["بنات… طحت لكم على موقع!", "دِيل بلس — كل أكواد الخصم بمكان واحد",
          "اختاري المتجر، انسخي الكود، الصقيه عند الدفع", "مرتّب بأقسام لكل شي تبينه",
          "احفظي متاجرك في المفضّلة", "وفيه بوت تيليجرام — الكود يجيك فوراً",
          "مجاني بالكامل — الرابط في البايو"],
    "2": ["بنات… طحت لكم على موقع!", "ليش تدفعين كامل وفيه كود خصم؟",
          "تختارين، تنسخين، تلصقين… والسعر ينزل", "كل الأقسام تحت إيدك",
          "متاجرك المفضّلة محفوظة", "أو خذي الكود من بوت تيليجرام فوراً",
          "بلا اشتراك ولا رسوم — الرابط في البايو"],
    "3": ["بنات… طحت لكم على موقع!", "خلّوني أوريكم كيف يشتغل",
          "انسخي الكود… شوفوا السعر نزل!", "أزياء، أكل، إلكترونيات، عطور، أطفال",
          "احفظي متاجرك عشان ما تدورين", "والبوت أسرع — اكتبي اسم المتجر",
          "مجاني بالكامل — جربوه قبل أي طلب"],
}
_SEQ = [
    ("hook", 4.0), ("concept", 5.0), ("phone", 9.5), ("categories", 6.0),
    ("favorites", 4.5), ("bot", 8.0), ("cta", 6.0),
]


def _build_beats(script_id: str) -> list[dict]:
    caps = _CAPTIONS[script_id]
    beats = []
    for (stype, dur), cap in zip(_SEQ, caps):
        beats.append({
            "type": stype, "dur": dur,
            "cap": _multiline_sprite(cap, _font(52), WHITE, W - 260),
        })
    return beats


def render_explainer(script_id: str, out_path: str, ffmpeg: str = "ffmpeg") -> str:
    beats = _build_beats(script_id)
    total = sum(b["dur"] for b in beats)
    nframe = int(total * FPS)
    parts = _particles(seed=7 + int(script_id))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-",
        "-vf", f"fade=t=in:st=0:d=0.4,fade=t=out:st={total-0.5:.2f}:d=0.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
        "-preset", "veryfast", "-movflags", "+faststart", out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        # حدود المشاهد الزمنية
        bounds, acc = [], 0.0
        for b in beats:
            bounds.append((acc, acc + b["dur"], b)); acc += b["dur"]
        for i in range(nframe):
            t = i / FPS
            beat = bounds[-1]
            for b0, b1, bb in bounds:
                if b0 <= t < b1:
                    beat = (b0, b1, bb); break
            b0, b1, bb = beat
            img = _base_background().copy()
            _chrome(img, parts, t)
            SCENES[bb["type"]](img, t - b0, bb["dur"])
            _caption(img, bb["cap"], t - b0, bb["dur"])
            proc.stdin.write(img.convert("RGB").tobytes())
        proc.stdin.close()
        err = proc.stderr.read()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed:\n{err.decode('utf-8','ignore')[-800:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out_path


def main(argv: Iterable[str] | None = None) -> None:
    import argparse, sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="مولّد فيديو شرح الموقع/البوت")
    ap.add_argument("--script", type=str, default="1", choices=["1", "2", "3"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", type=str, default="out_explainer")
    args = ap.parse_args(list(argv) if argv is not None else None)
    os.makedirs(args.out, exist_ok=True)
    ids = ["1", "2", "3"] if args.all else [args.script]
    for sid in ids:
        path = os.path.join(args.out, f"explainer_{sid}.mp4")
        print(f"[{sid}] rendering → {path}")
        render_explainer(sid, path)
        print(f"    done: {path}")


if __name__ == "__main__":
    main()
