# -*- coding: utf-8 -*-
"""نبض الصفقات — الهوية البصرية كمصدر واحد للحقيقة (بايثون).

هذا الملف هو **النظير البرمجي لدليل الهوية**. القيم منسوخة حرفياً من
`outreach/company_profile/style.css` — وهو نفسه مصدر ملفَّي الدليل PDF —
فلا يوجد هنا اشتقاق ولا تقريب ولا «قريب بالعين».

## لماذا وُجد هذا الملف

قبله كانت الهوية موزّعة على **خمس لوحات خاصّة متباينة**، قِيست ٢٠٢٦-٠٨-١٧:

| الموضع | الحبر | الأرضية | الخط |
|---|---|---|---|
| `dashboard.py` استوديو | `(31,41,55)` | كريمي→نعناعي | Noto |
| `api/social/ig_slides.py` | `(31,41,55)` | كريمي→نعناعي | Noto |
| `api/social/content_reels.py` | — | أخضر-فحمي `(9,33,27)` | Noto |
| `api/social/reels_render.py` | — | أخضر-فحمي + **ذهبي** | Noto |
| `deal_pulse_bot.py` ترحيب | `#0F172A` | من ركن اللوقو | Noto |

ولا واحدة منها تطابق حبر العلامة `#141C31`. واثنتان تجعلان **الأخضر أرضيةً**
بينما الدليل يقول نصّاً: الأخضر لهجة لا خلفية، ونسبته تحت ١٠–١٥٪. والذهبي
لون سادس لا وجود له في لوحة مغلقة.

## قواعد ملزِمة (مقيسة لا مذوَّقة)

- **الأخضر الفاتح يُرى ولا يُقرأ.** `G_500` مع نصّ أبيض = **2.54:1** — يسقط
  حتى لعنوان كبير (الحدّ ٣:١). أي سطح أخضر يحمل نصّاً ⇒ `G_700` (**5.48:1**).
- **الأرضية الداكنة هي حبر العلامة نفسه** `#141C31`، لا لون داكن مخترع.
- **الأحمر وظيفي لا هويّاتي**: خطر/فقد/«لا تفعل». لا يدخل خلفيةً ولا عنواناً
  ولا أي مادة ترويجية.
- **الخط عائلة واحدة**: IBM Plex Sans Arabic. سببه وظيفي لا ذوقي —
  `Cairo-Bold.ttf` في هذا المستودع يرسم **صفر بكسل** لجملة عربية كاملة بينما
  يُرجع عرضاً غير صفري، أي يفشل صامتاً (قِيس ٢٠٢٦-٠٨-١٧). وPlex وحدها كاملة
  أشكال العرض `U+FE95`/`U+FE8D` التي يحتاجها `arabic_reshaper`.
"""
from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))

# ═══ اللوحة المغلقة ═══════════════════════════════════════════════════════
INK_900 = (0x14, 0x1C, 0x31)   # #141C31 · حبر العلامة — عناوين وأسطح داكنة
INK_700 = (0x2C, 0x3A, 0x55)   # #2C3A55 · نصّ المتن
INK_500 = (0x55, 0x63, 0x7E)   # #55637E · التسميات والحواشي
LINE    = (0xE3, 0xE8, 0xEF)   # #E3E8EF · إطار البطاقات والفواصل

G_700   = (0x04, 0x78, 0x57)   # #047857 · الأخضر الحامل — أي سطح يحمل نصّاً
G_600   = (0x05, 0x96, 0x69)   # #059669 · الأخضر الرسومي — أسهم وأيقونات
G_500   = (0x10, 0xB9, 0x81)   # #10B981 · أخضر النبض — العلامة والزخرفة
G_50    = (0xEC, 0xFD, 0xF5)   # #ECFDF5 · خلفية بطاقة مميّزة

PAPER   = (0xFF, 0xFF, 0xFF)
SURFACE = (0xF7, 0xF9, 0xFB)
DANGER  = (0xB4, 0x23, 0x18)   # #B42318 · وظيفي فقط

# ═══ السلّم الداكن — حيث تنقلب الأدوار ════════════════════════════════════
DARK_GROUND    = INK_900              # الأرضية = حبر العلامة نفسه
DARK_RAISED    = (0x1B, 0x24, 0x40)   # #1B2440 · سطح مرتفع
DARK_HAIRLINE  = INK_700              # #2C3A55 · حدّ شعري
DARK_BODY      = LINE                 # #E3E8EF · متن — 13.75:1
DARK_SECONDARY = (0xC3, 0xCB, 0xDA)   # #C3CBDA · ثانوي — 9.38:1 على المرتفع
DARK_CAPTION   = (0x9A, 0xA6, 0xBC)   # #9AA6BC · حواشٍ — 6.90:1 على الأرضية
DARK_CARRY     = G_500                # على الداكن ينقلب الحامل إلى g-500 (6.68:1)
DANGER_DARK    = (0xE9, 0x63, 0x58)   # #E96358 · مشتقّ: 5.15:1 على الأرضية

# ═══ الخط ═════════════════════════════════════════════════════════════════
_FONT_DIR = os.path.join(_HERE, "assets", "fonts")

#: الأوزان الأربعة المسموحة في الدليل — لا غيرها.
FONT_WEIGHTS = (400, 500, 600, 700)

#: مرشّحو الخط بالترتيب. Plex أولاً (عائلة الهوية)، ثم Noto كشبكة أمان على
#: بيئة ناقصة، ثم DejaVu على لينكس. **Cairo محذوف عمداً**: نسخته هنا لاتينية
#: فقط وتفشل صامتة — إبقاؤه في القائمة يعني أن عطباً قديماً قد يعود بلا إنذار.
def font_path(weight: int = 700) -> str | None:
    """يرجّع مسار خطّ الهوية للوزن المطلوب، أو أقرب بديل متاح، أو None."""
    if weight not in FONT_WEIGHTS:
        weight = min(FONT_WEIGHTS, key=lambda w: abs(w - weight))
    ordered = [os.path.join(_FONT_DIR, f"IBMPlexSansArabic-{weight}.ttf")]
    ordered += [os.path.join(_FONT_DIR, f"IBMPlexSansArabic-{w}.ttf")
                for w in (700, 600, 500, 400) if w != weight]
    ordered += [
        os.path.join(_HERE, "NotoSansArabic-Bold.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    return next((p for p in ordered if os.path.exists(p)), None)


def font(size: int, weight: int = 700):
    """‏`ImageFont` بخطّ الهوية. يرمي ImportError لو Pillow غائب."""
    from PIL import ImageFont
    p = font_path(weight)
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


# ═══ فحص التباين — الدليل §التباين ════════════════════════════════════════
def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    """نسبة تباين WCAG 2.1. الحدّ ٤٫٥:١ للنصّ الصغير و٣:١ للكبير والواجهة."""
    a, b = relative_luminance(fg), relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def on_green(large: bool = False) -> tuple[int, int, int]:
    """يرجّع الأخضر الصالح كأرضية تحمل نصّاً أبيض — دائماً g-700.

    مُبقىً كدالة لا كثابت كي يبقى السبب ملتصقاً بالاستدعاء: g-500/g-600
    يسقطان مع الأبيض (2.54 و3.77)، وg-700 يمرّ بـ5.48.
    """
    return G_700


def hex_of(rgb: tuple[int, int, int]) -> str:
    return "#%02X%02X%02X" % rgb
