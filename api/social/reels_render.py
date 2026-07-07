"""مولّد ريلز متحرّك (Programmatic) بهوية «Dark Luxe» — كروت أكواد من master.

يبني فيديو عمودي 1080×1920 (9:16) بحركة حقيقية: خلفية زمردية-فحمية متدرّجة،
توهّج، جزيئات ذهبية طافية، لوقو، اسم المتجر يظهر بتكبير مرن، قيمة الخصم تنبض،
شريحة الكود بلمعان (shimmer) يمرّ عليها، ونداء ختامي نابض. لا صوت (يُضاف لاحقاً).

المصدر: جدول master (بيانات حقيقية) — اسم المتجر + خصم العميل + الكود.
التقنية: Pillow يرسم كل فريم → يُبثّ خام إلى ffmpeg (بلا ملفات مؤقتة) → MP4/H.264.
تبعيات: Pillow + numpy + arabic_reshaper + python-bidi + ffmpeg (كلها متوفّرة).

تشغيل:
    python -m api.social.reels_render --limit 3 --out out_reels
    python -m api.social.reels_render --store "نون" --out out_reels
"""
from __future__ import annotations

import io
import math
import os
import random
import re
import subprocess
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

from api.social.ig_slides import _shape_ar  # تشكيل عربي موحّد

# ─── أبعاد وتوقيت ───────────────────────────────────────────────────────────
W, H   = 1080, 1920
FPS    = 30
DUR    = 7.0                      # ثوانٍ
NFRAME = int(FPS * DUR)
MARGIN = 96

# ─── لوحة Dark Luxe (زمردي + ذهبي) ─────────────────────────────────────────
BG_TOP    = (9, 33, 27)
BG_BOTTOM = (3, 12, 9)
EMERALD        = (16, 185, 129)
EMERALD_BRIGHT = (52, 211, 153)
EMERALD_DEEP   = (6, 78, 59)
GOLD        = (214, 178, 94)
GOLD_BRIGHT = (241, 214, 143)
WHITE = (255, 255, 255)
MUTED = (150, 176, 165)
INK   = (5, 26, 20)
CHIP  = (12, 38, 31)

_ROOT      = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_FONT_PATH = os.path.join(_ROOT, "NotoSansArabic-Bold.ttf")
_LOGO      = os.path.join(_ROOT, "logo_for_watermark.png")

_AR_NUMS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


# ─── تيسير (easing) ─────────────────────────────────────────────────────────
def clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def seg(t: float, a: float, b: float) -> float:
    """تقدّم مطبَّع 0→1 داخل النافذة [a,b] (ثوانٍ)."""
    return clamp01((t - a) / (b - a)) if b > a else 1.0


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t: float, s: float = 1.70158) -> float:
    t -= 1
    return 1 + (s + 1) * t ** 3 + s * t ** 2


# ─── خطوط وأصول ─────────────────────────────────────────────────────────────
_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def _font(size: int) -> ImageFont.FreeTypeFont:
    f = _FONT_CACHE.get(size)
    if f is None:
        f = ImageFont.truetype(_FONT_PATH, size)
        _FONT_CACHE[size] = f
    return f


_BASE_CACHE: Image.Image | None = None
_LOGO_CACHE: Image.Image | None = None


def _base_background() -> Image.Image:
    """خلفية ثابتة (تدرّج + توهّجان مموّهان) تُحسب مرة وتُنسخ لكل فريم."""
    global _BASE_CACHE
    if _BASE_CACHE is not None:
        return _BASE_CACHE
    img = Image.new("RGBA", (W, H), (*BG_BOTTOM, 255))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(
            int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t),
            int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t),
            int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t), 255))
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 620, -420, W + 380, 520], fill=(*EMERALD, 46))      # زمردي أعلى يمين
    gd.ellipse([-360, H - 560, 460, H + 360], fill=(*GOLD, 26))         # ذهبي أسفل يسار
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(190)))
    # فينييت خفيف لتركيز المركز
    vig = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vig).ellipse([-W * 0.35, -H * 0.12, W * 1.35, H * 1.12], fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(240))
    dark = Image.new("RGBA", (W, H), (0, 0, 0, 130))
    dark.putalpha(ImageChops.invert(vig).point(lambda p: int(p * 0.5)))
    img.alpha_composite(dark)
    _BASE_CACHE = img
    return img


def _logo_sprite() -> Image.Image | None:
    global _LOGO_CACHE
    if _LOGO_CACHE is not None:
        return _LOGO_CACHE
    if not os.path.exists(_LOGO):
        return None
    logo = Image.open(_LOGO).convert("RGBA")
    tw = 300
    logo = logo.resize((tw, int(logo.height * tw / logo.width)), Image.LANCZOS)
    _LOGO_CACHE = logo
    return logo


# ─── نصوص كصور (سبرايت) لتمكين التكبير/التلاشي ──────────────────────────────
def _text_sprite(text: str, font: ImageFont.FreeTypeFont, fill,
                 glow: tuple | None = None) -> Image.Image:
    """يرسم نصاً عربياً مشكّلاً على صورة شفّافة مقصوصة (مع توهّج اختياري)."""
    shaped = _shape_ar(text)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bb = probe.textbbox((0, 0), shaped, font=font)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    pad = 40
    s = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(s)
    ox, oy = pad - bb[0], pad - bb[1]
    if glow:
        gl = Image.new("RGBA", s.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).text((ox, oy), shaped, font=font, fill=(*glow, 255))
        s.alpha_composite(gl.filter(ImageFilter.GaussianBlur(18)))
    sd.text((ox, oy), shaped, font=font, fill=fill)
    return s


def _paste_center(img: Image.Image, sprite: Image.Image, cy: float,
                  scale: float = 1.0, alpha: float = 1.0) -> None:
    if scale <= 0.01 or alpha <= 0.01:
        return
    w = max(1, int(sprite.width * scale))
    h = max(1, int(sprite.height * scale))
    sp = sprite if (w == sprite.width and h == sprite.height) else sprite.resize((w, h), Image.LANCZOS)
    if alpha < 0.99:
        sp = sp.copy()
        sp.putalpha(sp.split()[3].point(lambda p: int(p * alpha)))
    img.alpha_composite(sp, ((W - w) // 2, int(cy - h / 2)))


# ─── جزيئات طافية (ذهبي/زمردي) ──────────────────────────────────────────────
def _particles(seed: int, n: int = 46) -> list[dict]:
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        out.append(dict(
            x=rnd.uniform(0, W), y=rnd.uniform(0, H),
            r=rnd.uniform(1.6, 4.8), spd=rnd.uniform(14, 46),
            ph=rnd.uniform(0, 6.28), amp=rnd.uniform(6, 26),
            gold=rnd.random() < 0.45,
        ))
    return out


def _draw_particles(img: Image.Image, parts: list[dict], t: float) -> None:
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for p in parts:
        y = (p["y"] - p["spd"] * t) % H
        x = p["x"] + math.sin(t * 1.15 + p["ph"]) * p["amp"]
        a = int(70 + 55 * math.sin(t * 2.1 + p["ph"]))
        a = max(18, min(130, a))
        col = GOLD_BRIGHT if p["gold"] else EMERALD_BRIGHT
        r = p["r"]
        d.ellipse([x - r, y - r, x + r, y + r], fill=(*col, a))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.6)))


# ─── لمعان (shimmer) يمرّ فوق شريحة الكود ────────────────────────────────────
def _shimmer(img: Image.Image, box: tuple, radius: int, t: float, period: float = 2.2) -> None:
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    band = Image.new("L", (w, h), 0)
    bd = ImageDraw.Draw(band)
    pos = (t % period) / period
    cx = int(-w * 0.4 + pos * (w * 1.8))
    for i in range(-70, 70):
        a = int(150 * max(0.0, 1 - abs(i) / 70))
        if a:
            bd.line([(cx + i, -20), (cx + i - h, h + 20)], fill=a, width=3)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    band = ImageChops.multiply(band, mask)
    hi = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    hi.putalpha(band)
    img.alpha_composite(hi, (x0, y0))


def _rounded(img: Image.Image, box, radius, fill, outline=None, ow=2, shadow=True) -> None:
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        x0, y0, x1, y1 = box
        ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 22, x1, y1 + 22], radius=radius, fill=(0, 0, 0, 130))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(38)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius=radius, fill=fill)
    if outline:
        d.rounded_rectangle(box, radius=radius, outline=outline, width=ow)


# ─── تركيب فريم واحد ────────────────────────────────────────────────────────
def _compose(store: dict, sprites: dict, parts: list[dict], t: float) -> Image.Image:
    img = _base_background().copy()
    _draw_particles(img, parts, t)

    # لوقو (تلاشٍ + هبوط طفيف)
    logo = _logo_sprite()
    if logo is not None:
        a = ease_out_cubic(seg(t, 0.0, 0.6))
        dy = (1 - a) * 24
        lg = logo
        if a < 0.99:
            lg = logo.copy(); lg.putalpha(lg.split()[3].point(lambda p: int(p * a)))
        img.alpha_composite(lg, ((W - logo.width) // 2, int(150 + dy)))

    # kicker «كود خصم حصري» (تلاشٍ + صعود)
    a = ease_out_cubic(seg(t, 0.35, 1.05))
    _paste_center(img, sprites["kicker"], 470 - (1 - a) * 26, 1.0, a)

    # اسم المتجر (تكبير مرن back + تلاشٍ)
    p = seg(t, 0.7, 1.7)
    _paste_center(img, sprites["store"], 660, 0.6 + ease_out_back(p) * 0.4, ease_out_cubic(min(1, p * 1.4)))

    # خصم العميل (نبض بعد الظهور)
    p = seg(t, 1.5, 2.4)
    pulse = 1 + 0.03 * math.sin(max(0, t - 2.4) * 4.2) if p >= 1 else 1
    _paste_center(img, sprites["benefit"], 900,
                  (0.7 + ease_out_back(p) * 0.3) * pulse, ease_out_cubic(min(1, p * 1.5)))

    # شريحة الكود (انزلاق للأعلى + تلاشٍ + لمعان)
    if sprites.get("code"):
        cp = seg(t, 2.2, 3.05)
        ca = ease_out_cubic(cp)
        cy = 1200 + (1 - ease_out_back(cp)) * 60
        chip_w, chip_h, rad = 760, 210, 42
        box = ((W - chip_w) // 2, int(cy), (W + chip_w) // 2, int(cy) + chip_h)
        if ca > 0.02:
            tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            _rounded(tmp, box, rad, (*CHIP, 250), outline=(*GOLD, 255), ow=3)
            label = _text_sprite("كود الخصم", _font(40), EMERALD_BRIGHT)
            tmp.alpha_composite(label, ((W - label.width) // 2, box[1] + 26))
            tmp.alpha_composite(sprites["code"], ((W - sprites["code"].width) // 2, box[1] + 78))
            if ca < 0.99:
                tmp.putalpha(tmp.split()[3].point(lambda p: int(p * ca)))
            img.alpha_composite(tmp)
            if cp >= 1:
                _shimmer(img, box, rad, t)

    # «انسخه والصقه عند الدفع» (يظهر بعد الشريحة)
    a = ease_out_cubic(seg(t, 3.2, 3.9))
    _paste_center(img, sprites["howto"], 1470 - (1 - a) * 18, 1.0, a)

    # نداء ختامي: pill نابض
    cta_p = seg(t, 4.6, 5.3)
    if cta_p > 0.02:
        beat = 1 + 0.035 * math.sin(max(0, t - 5.3) * 4.0)
        spr = sprites["cta"]
        scale = (0.8 + ease_out_back(cta_p) * 0.2) * beat
        w = int(spr.width * scale); h = int(spr.height * scale)
        px0 = (W - w) // 2 - 60; py0 = 1640
        pill = ((px0, py0, px0 + w + 120, py0 + h + 46))
        tmp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _rounded(tmp, pill, (h + 46) // 2, (*EMERALD, 255), shadow=True)
        sp = spr.resize((w, h), Image.LANCZOS)
        tmp.alpha_composite(sp, (px0 + 60, py0 + 23))
        if cta_p < 0.99:
            tmp.putalpha(tmp.split()[3].point(lambda p: int(p * ease_out_cubic(cta_p))))
        img.alpha_composite(tmp)

    # فوتر ثابت
    d = ImageDraw.Draw(img)
    fs = sprites["footer"]
    img.alpha_composite(fs, ((W - fs.width) // 2, H - 96))
    return img


def _build_sprites(store: dict) -> dict:
    benefit = store["benefit"]
    code = store.get("code")
    sprites = {
        "kicker":  _text_sprite("كود خصم حصري", _font(46), GOLD_BRIGHT),
        "store":   _text_sprite(store["name"], _font(96), WHITE, glow=EMERALD_DEEP),
        "benefit": _text_sprite(benefit, _font(118 if len(benefit) <= 5 else 84),
                                EMERALD_BRIGHT, glow=EMERALD_DEEP),
        "howto":   _text_sprite("انسخه والصقه عند الدفع", _font(44), MUTED),
        "cta":     _text_sprite("الرابط في البايو", _font(56), INK),
        "footer":  _text_sprite("@dealpulseksa  ·  نبض الصفقات", _font(34), MUTED),
    }
    if code:
        sprites["code"] = _text_sprite(code, _font(92), GOLD_BRIGHT)
    return sprites


# ─── رندر MP4 عبر بثّ خام إلى ffmpeg ────────────────────────────────────────
def render_reel(store: dict, out_path: str, ffmpeg: str = "ffmpeg") -> str:
    """يرندر ريل واحد (7s) إلى out_path. store: {name, benefit, code?}."""
    sprites = _build_sprites(store)
    parts = _particles(seed=abs(hash(store["name"])) % (2 ** 31))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-vf", "fade=t=in:st=0:d=0.4,fade=t=out:st=6.5:d=0.5",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18",
        "-preset", "veryfast", "-movflags", "+faststart", out_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE)
    try:
        for i in range(NFRAME):
            frame = _compose(store, sprites, parts, i / FPS)
            proc.stdin.write(frame.convert("RGB").tobytes())
        proc.stdin.close()
        err = proc.stderr.read()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed:\n{err.decode('utf-8', 'ignore')[-800:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
    return out_path


# ─── تحميل متاجر حقيقية من master ───────────────────────────────────────────
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{2,13}$")
_LINK_HINTS = ("رابط", "الدخول", "الشراء", "كلام", "على حسب", "ثابت", "%", "$")


def _clean_code(public_coupon: str | None) -> str | None:
    """يُرجع كوداً صالحاً للعرض، أو None لو النص إرشادي (استخدم الرابط…)."""
    if not public_coupon:
        return None
    c = public_coupon.strip()
    return c.upper() if _CODE_RE.match(c) else None


def load_stores(limit: int | None = None, only: str | None = None) -> list[dict]:
    import psycopg2
    url = None
    for line in open(os.path.join(_ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if line.startswith("DATABASE_URL"):
            url = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not url:
        raise RuntimeError("DATABASE_URL غير موجود في .env")
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("""
        select store_id, public_coupon, discount_value
        from master
        where coalesce(affiliate_link,'')<>''
          and coalesce(is_suspended,false)=false
          and coalesce(discount_value,'')<>''
          and (%s is null or store_id = %s)
        order by (coalesce(total_coupon_copies,0)+coalesce(total_link_clicks,0)) desc
    """, (only, only))
    rows = cur.fetchall()
    conn.close()
    out = []
    for name, coupon, disc in rows:
        out.append({"name": name.strip(), "benefit": disc.strip(),
                    "code": _clean_code(coupon)})
        if limit and len(out) >= limit:
            break
    return out


def _slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z؀-ۿ]+", "_", name).strip("_") or "reel"


def main(argv: Iterable[str] | None = None) -> None:
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="مولّد ريلز أكواد متحرّك")
    ap.add_argument("--limit", type=int, default=3)
    ap.add_argument("--store", type=str, default=None, help="اسم متجر محدّد (store_id)")
    ap.add_argument("--out", type=str, default="out_reels")
    args = ap.parse_args(list(argv) if argv is not None else None)

    stores = load_stores(limit=args.limit, only=args.store)
    if not stores:
        print("لا توجد متاجر مطابقة."); return
    os.makedirs(args.out, exist_ok=True)
    for i, s in enumerate(stores, 1):
        path = os.path.join(args.out, f"{i:02d}_{_slug(s['name'])}.mp4")
        print(f"[{i}/{len(stores)}] {s['name']} — خصم {s['benefit']} — كود {s['code'] or '—'}")
        render_reel(s, path)
        print(f"    ✓ {path}")


if __name__ == "__main__":
    main()
