# -*- coding: utf-8 -*-
"""فاحص الفيض — يمسك القصّ الصامت في صفحات البروفايل.

**المشكلة التي يحلّها:** ‏`.page` ارتفاعها ثابت `297mm` مع `overflow:hidden`،
فإذا زاد المحتوى عن الصفحة **يُقصّ بصمت**: عدد صفحات الـPDF يبقى كما هو، ولا
رسالة خطأ، والسطر المفقود لا يُكتشف إلا بعين تقرأ الملف كاملاً.

**الآلية:** نعيد الطباعة بنسخة مُعدَّلة تُلغي القصّ (`height:auto` +
`overflow:visible`). عندها الصفحة الفائضة **تنسكب إلى ورقة إضافية**، فيصير
عدد أوراق الـPDF أكبر من عدد أقسام `.page`. الفرق = عدد الصفحات الفائضة.

    python outreach/company_profile/check_overflow.py

يفحص النسخ الثلاث (عربي · إنجليزي · المدمج). المدمج يُفحص أيضاً لأن الغلاف
الداخلي `<div lang="en">` قد يغيّر التخطيط، فلا يكفي أن تكون النسختان نظيفتين.

يرجّع 0 لو كل الصفحات ضمن حدّها، و1 لو فاضت أي صفحة.
"""
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_pdf import (  # noqa: E402
    EDITIONS, LOGO, SECTION_RE, edition_html, find_browser, logo_data_uri,
)

# إلغاء الحدّ الصارم: الارتفاع يتمدّد والفيض يظهر بدل أن يُقصّ.
PROBE_CSS = """
<style id="overflow-probe">
  .page{ height:auto !important; min-height:297mm !important; overflow:visible !important; }
</style>
"""


def pdf_page_count(path: pathlib.Path) -> int:
    """عدّ أوراق الـPDF بلا مكتبة خارجية.

    كروميوم يكتب `/Type /Page` لكل ورقة و`/Type /Pages` لعقدة الشجرة —
    فالحدّ `(?![s])` يستبعد الثانية. وإن فشل النمط نرجع لـ`/Count N`.
    """
    raw = path.read_bytes()
    pages = len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", raw))
    if pages:
        return pages
    counts = [int(m) for m in re.findall(rb"/Count\s+(\d+)", raw)]
    return max(counts) if counts else 0


def probe(key: str, data_uri: str, browser: str) -> int:
    html = edition_html(key, data_uri)
    sections = len(SECTION_RE.findall(html))

    # نحقن التجاوز قبل </head> كي يأتي بعد ورقة الأنماط فيغلبها.
    html = html.replace("</head>", PROBE_CSS + "</head>", 1)
    probe_html = HERE / f"_probe_{key}.html"
    probe_pdf = HERE / f"_probe_{key}.pdf"
    probe_html.write_text(html, encoding="utf-8")

    cmd = [
        browser, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=15000",
        "--no-pdf-header-footer", f"--print-to-pdf={probe_pdf}", probe_html.as_uri(),
    ]
    subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if not probe_pdf.exists():
        print(f"  {key.upper():4s}: !! probe PDF not produced")
        return 1

    sheets = pdf_page_count(probe_pdf)
    probe_html.unlink(missing_ok=True)
    probe_pdf.unlink(missing_ok=True)

    if sheets == sections:
        print(f"  {key.upper():4s}: ✓ {sections} صفحة، لا فيض")
        return 0
    print(f"  {key.upper():4s}: ✗ فيض — {sections} قسم .page لكن الطباعة أعطت {sheets} ورقة "
          f"({sheets - sections} صفحة تتجاوز حدّها)")
    return 1


def main() -> int:
    browser = find_browser()
    if browser is None:
        print("!! no Edge/Chrome/Chromium found")
        return 1
    if not LOGO.exists():
        print(f"!! logo missing: {LOGO}")
        return 1

    data_uri = logo_data_uri()
    print("فحص الفيض (height:auto + overflow:visible):")
    rc = 0
    for key in EDITIONS:
        rc |= probe(key, data_uri, browser)
    return rc


if __name__ == "__main__":
    sys.exit(main())
