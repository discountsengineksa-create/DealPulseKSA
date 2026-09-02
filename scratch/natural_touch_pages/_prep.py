"""يبني payloads.json من الـ36 ملف: ينظّف رابط التتبّع + يجهّز العنوان/الكلمة/الوصف.
الربط الداخلي يُضاف في تمريرة ثانية بعد معرفة الـ slugs (سكربت النشر)."""
import json, re, pathlib

HERE = pathlib.Path(__file__).parent
# رابط التتبّع (Google Merchant srsltid) مثبّت حرفياً في الـ36 — يُجرّد إلى نص عادي.
# صندوق الكوبون (M13 / خصم 10%) يعرضه قالب /c/{slug} من master تلقائياً.
LINK_RE = re.compile(r"\[([^\]]+)\]\(https://ntshop\.sa/\?srsltid=[^)]*\)")
SRSLTID = "https://ntshop.sa/?srsltid=AfmBOor0tUYH9fnN34zXCdkz7NmKdY3fmVZoXI4qfYPDS_USQrV_bX_W"

SECTIONS = {
    "hair": range(1, 11), "skin": range(11, 19), "body": range(19, 23),
    "makeup": range(23, 26), "perfume": range(26, 30), "relax": range(30, 32),
    "gifts": range(32, 35), "home": range(35, 37),
}
def section_of(n):
    for s, r in SECTIONS.items():
        if n in r:
            return s
    return "misc"

out = []
for f in sorted(HERE.glob("[0-9][0-9]_*.md")):
    n = int(f.name[:2])
    if n == 0:
        continue
    raw = f.read_text(encoding="utf-8")
    body = LINK_RE.sub(r"\1", raw)
    lines = body.splitlines()
    title = next(l[2:].strip() for l in lines if l.startswith("# "))
    kw = f.name[3:-3].replace("_", " ").strip()
    # الوصف: أول فقرة نصّية حقيقية
    desc = ""
    for l in lines[1:]:
        s = l.strip()
        if s and not s.startswith("#"):
            desc = re.sub(r"\s+", " ", s)[:280]
            break
    out.append({
        "file": f.name, "n": n, "section": section_of(n),
        "title": title, "target_keyword": kw, "description": desc,
        "body_markdown": body, "master_id": 74, "lang": "ar",
    })

(HERE / "_payloads.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {len(out)} payloads")
for p in out:
    assert SRSLTID not in p["body_markdown"], p["file"]
    w = len(re.findall(r"\S+", p["body_markdown"]))
    print(f"  {p['n']:2d} [{p['section']:7s}] {w:4d}w  {p['target_keyword']}")
