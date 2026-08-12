# -*- coding: utf-8 -*-
"""يبني ملف البروفايل PDF من profile.html.

يحقن الشعار كـdata URI (كي لا يعتمد الـPDF على مسار خارجي)، ثم يطبع عبر
Edge/Chrome headless. شغّله بعد أي تعديل على profile.html:

    python outreach/company_profile/build_pdf.py
"""
import base64
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE / "profile.html"
BUILD = HERE / "_build.html"
OUT = HERE / "DealPulse_Profile_AR.pdf"
LOGO = pathlib.Path(r"C:\Users\PC\Desktop\dealpulseksa-web\public\logo.png")

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

def main() -> int:
    if not LOGO.exists():
        print(f"!! logo missing: {LOGO}")
        return 1

    data_uri = "data:image/png;base64," + base64.b64encode(LOGO.read_bytes()).decode("ascii")
    html = SRC.read_text(encoding="utf-8").replace("__LOGO__", data_uri)
    BUILD.write_text(html, encoding="utf-8")
    print(f"built  {BUILD.name}  ({BUILD.stat().st_size:,} bytes)")

    browser = next((b for b in BROWSERS if os.path.exists(b)), None)
    if browser is None:
        print("!! no Edge/Chrome found")
        return 1

    if OUT.exists():
        OUT.unlink()

    cmd = [
        browser,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=10000",
        "--no-pdf-header-footer",
        f"--print-to-pdf={OUT}",
        BUILD.as_uri(),
    ]
    print("printing via", os.path.basename(browser))
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.stderr.strip():
        print(proc.stderr.strip()[:600])

    if OUT.exists() and OUT.stat().st_size > 0:
        print(f"OK     {OUT}  ({OUT.stat().st_size:,} bytes)")
        return 0
    print("!! PDF not produced (exit %s)" % proc.returncode)
    return 1


if __name__ == "__main__":
    sys.exit(main())
