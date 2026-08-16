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
# تمريرتان — لأن الفيض صنفان لا صنف واحد:
#
#  أ) **المحتوى أطول من الصفحة.** يُكشف بارتفاع حرّ: الصفحة تنسكب لورقة ثانية.
#     ولا بدّ من تحييد `margin-top:auto` و`flex:1`، وإلا انهارا مع الارتفاع الحرّ
#     فبدا المحتوى مناسباً.
#  ب) **التوزيع يدفع عنصراً خارج الصفحة** مع بقاء الارتفاع الثابت — كعنصر أسفل
#     صفحة flex. الارتفاع المكدّس هنا **أقلّ** من 297mm فتمريرة (أ) تمرّره، لكنه
#     يُقصّ فعلياً. يُكشف بإبقاء الارتفاع ثابتاً وفتح `overflow` وحده.
#
# (ب) أمسكت قصّ شريط التواصل في غلاف دليل الهوية بعدما مرّرته (أ).
PROBE_STACKED = """
<style id="overflow-probe">
  .page{ height:auto !important; min-height:297mm !important; overflow:visible !important; }
  .cover-body{ flex:none !important; }
  .foot, .cover-foot, .cover-pillars{ margin-top:0 !important; }
</style>
"""

PROBE_SPILL = """
<style id="overflow-probe">
  .page{ overflow:visible !important; }
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


def _sheets(key, html, css, browser, tag):
    html = html.replace("</head>", css + "</head>", 1)
    ph = HERE / f"_probe_{key}_{tag}.html"
    pp = HERE / f"_probe_{key}_{tag}.pdf"
    ph.write_text(html, encoding="utf-8")
    subprocess.run([
        browser, "--headless=new", "--disable-gpu", "--no-sandbox",
        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=15000",
        "--no-pdf-header-footer", f"--print-to-pdf={pp}", ph.as_uri(),
    ], capture_output=True, text=True, timeout=180)
    n = pdf_page_count(pp) if pp.exists() else -1
    ph.unlink(missing_ok=True); pp.unlink(missing_ok=True)
    return n


def probe(key: str, data_uri: str, browser: str) -> int:
    html = edition_html(key, data_uri)
    sections = len(SECTION_RE.findall(html))

    stacked = _sheets(key, html, PROBE_STACKED, browser, "a")
    spill = _sheets(key, html, PROBE_SPILL, browser, "b")

    if stacked == sections and spill == sections:
        print(f"  {key.upper():5s}: ✓ {sections} صفحة — لا فيض ولا قصّ")
        return 0
    bad = []
    if stacked != sections:
        bad.append(f"محتوى أطول من الصفحة (+{stacked - sections})")
    if spill != sections:
        bad.append(f"عنصر يُدفع خارج الصفحة (+{spill - sections})")
    print(f"  {key.upper():5s}: ✗ {sections} قسم — " + " · ".join(bad))
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
