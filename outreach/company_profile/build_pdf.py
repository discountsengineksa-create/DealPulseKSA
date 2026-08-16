# -*- coding: utf-8 -*-
"""يبني ملفات البروفايل PDF من profile.html و profile_en.html.

ثلاث نسخ:
  ar   — عربي وحده        → DealPulse_Profile_AR.pdf
  en   — إنجليزي وحده     → DealPulse_Profile_EN.pdf
  both — عربي ثم إنجليزي  → DealPulse_Profile_AR_EN.pdf   (مستند واحد)

المدمج **يُولَّد من المصدرين وقت البناء، لا ملفّ ثالث** — فأي تعديل على النسختين
ينعكس عليه تلقائياً ولا يوجد نصّ يُصان مرّتين.

    python outreach/company_profile/build_pdf.py            # الثلاثة
    python outreach/company_profile/build_pdf.py both        # المدمج وحده

⚠️ ‏`.page` ارتفاعها ثابت 297mm مع `overflow:hidden` — أي فيض محتوى يُقصّ بصمت
ولا يظهر في عدد الصفحات. بعد أي تعديل على المحتوى شغّل الفاحص:

    python outreach/company_profile/check_overflow.py
"""
import base64
import os
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
# نسخة طباعة داخل الريبو (3360×2166 ⇒ ~908dpi عند عرض 94mm في الغلاف).
# كانت تشير إلى ريبو الويب — مسار خارجي يكسر البناء على أي جهاز ثانٍ.
LOGO = HERE / "logo_print.png"
# نسخة مفرَّغة (حبر أبيض بألفا + نبض #10B981 مصحَّح) للأرضيات الداكنة.
# مولَّدة من الأصل بإعادة كتابة اللوحة — لا تُحرَّر يدوياً.
LOGO_DARK = HERE / "logo_on_dark.png"

AR_SRC = HERE / "profile.html"
EN_SRC = HERE / "profile_en.html"
BRAND_SRC = HERE / "brand_guidelines.html"
BRAND_EN_SRC = HERE / "brand_guidelines_en.html"

# المفتاح → (ملف البناء الوسيط، المخرَج)
EDITIONS = {
    "ar":   (HERE / "_build_ar.html",   HERE / "DealPulse_Profile_AR.pdf"),
    "en":   (HERE / "_build_en.html",   HERE / "DealPulse_Profile_EN.pdf"),
    "both": (HERE / "_build_both.html", HERE / "DealPulse_Profile_AR_EN.pdf"),
    "brand": (HERE / "_build_brand.html", HERE / "DealPulse_Brand_Guidelines_AR.pdf"),
    "brand_en": (HERE / "_build_brand_en.html", HERE / "DealPulse_Brand_Guidelines_EN.pdf"),
}

SECTION_RE = re.compile(r'<section class="page.*?</section>', re.S)

BROWSERS = [
    # ويندوز (جهاز المالك)
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    # لينكس (جلسات السحابة / CI)
    "/opt/pw-browsers/chromium",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/microsoft-edge",
]


def find_browser():
    return next((b for b in BROWSERS if os.path.exists(b)), None)


def logo_data_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")


def edition_html(key: str, data_uri: str) -> str:
    """يرجّع HTML النسخة جاهزاً (الشعار محقون).

    المدمج: يأخذ الملف العربي كاملاً كقاعدة (جذره `lang=ar dir=rtl`)، ثم يُلحق
    أقسام الإنجليزي داخل `<div lang="en" dir="ltr">`. الأنماط تلتقط الغلاف الداخلي
    لأن محدّداتها `[lang="en"]` بلا `html` أمامها (انظر التعليق في style.css).
    """
    if key == "ar":
        return AR_SRC.read_text(encoding="utf-8").replace("__LOGO__", data_uri)
    if key == "en":
        return EN_SRC.read_text(encoding="utf-8").replace("__LOGO__", data_uri)
    if key in ("brand", "brand_en"):
        # الترتيب مقصود: `__LOGO_DARK__` أولاً، وإلا التهم `__LOGO__` بدايتَه.
        dark_uri = ("data:image/png;base64,"
                    + base64.b64encode(LOGO_DARK.read_bytes()).decode("ascii"))
        src = BRAND_SRC if key == "brand" else BRAND_EN_SRC
        return (src.read_text(encoding="utf-8")
                .replace("__LOGO_DARK__", dark_uri)
                .replace("__LOGO__", data_uri))

    ar = AR_SRC.read_text(encoding="utf-8")
    en = EN_SRC.read_text(encoding="utf-8")
    en_pages = "\n\n".join(SECTION_RE.findall(en))
    if not en_pages:
        raise SystemExit("!! no <section class=\"page\"> found in profile_en.html")
    block = (
        '\n<!-- ══════════════ English edition — same document ══════════════ -->\n'
        '<div lang="en" dir="ltr">\n\n' + en_pages + "\n\n</div>\n"
    )
    merged = ar.replace("</body>", block + "</body>", 1)
    merged = merged.replace(
        "<title>نبض الصفقات — الملف التعريفي</title>",
        "<title>نبض الصفقات — الملف التعريفي · Deal Pulse KSA — Company Profile</title>",
        1,
    )
    return merged.replace("__LOGO__", data_uri)


def build(key, data_uri, browser):
    build_html, out = EDITIONS[key]
    build_html.write_text(edition_html(key, data_uri), encoding="utf-8")
    print(f"built  {build_html.name}  ({build_html.stat().st_size:,} bytes)")

    if out.exists():
        out.unlink()

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=15000",
        "--no-pdf-header-footer",
        f"--print-to-pdf={out}",
        build_html.as_uri(),
    ]
    print(f"printing {key.upper()} via {os.path.basename(browser)}")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.stderr.strip():
        print(proc.stderr.strip()[:600])

    if out.exists() and out.stat().st_size > 0:
        print(f"OK     {out.name}  ({out.stat().st_size:,} bytes)")
        return 0
    print(f"!! PDF not produced for {key} (exit {proc.returncode})")
    return 1


def main() -> int:
    if not LOGO.exists():
        print(f"!! logo missing: {LOGO}")
        return 1
    wanted_now = sys.argv[1:] or list(EDITIONS)
    needed = {AR_SRC, EN_SRC}
    if "brand" in wanted_now: needed.add(BRAND_SRC)
    if "brand_en" in wanted_now: needed.add(BRAND_EN_SRC)
    for src in needed:
        if not src.exists():
            print(f"!! source missing: {src}")
            return 1

    wanted = [a.lower() for a in sys.argv[1:]] or list(EDITIONS)
    unknown = [w for w in wanted if w not in EDITIONS]
    if unknown:
        print(f"!! unknown edition(s): {', '.join(unknown)} — use: ar / en / both / brand / brand_en")
        return 1

    browser = find_browser()
    if browser is None:
        print("!! no Edge/Chrome/Chromium found")
        return 1

    data_uri = logo_data_uri()
    rc = 0
    for key in wanted:
        rc |= build(key, data_uri, browser)
    return rc


if __name__ == "__main__":
    sys.exit(main())
