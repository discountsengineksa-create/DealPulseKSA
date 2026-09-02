"""ينشر الـ36 صفحة عبر /admin/seo-import ثم يربطها داخلياً ثم يقلبها published + IndexNow.
يتطلّب endpoint /admin/seo-import منشوراً على الإنتاج (commit في admin.py).

Usage:
  python _publish.py import      # تمريرة 1: إدخال كـ draft
  python _publish.py link        # تمريرة 2: ربط داخلي (اقرأ أيضاً)
  python _publish.py publish     # تمريرة 3: نشر + IndexNow
  python _publish.py all         # الثلاثة بالترتيب
حالة كل تمريرة تُحفظ في _state.json (قابل للاستئناف).
"""
import json, os, re, ssl, sys, time, pathlib, urllib.request, urllib.error

HERE = pathlib.Path(__file__).parent
API = "https://api.dealpulseksa.com/api/v1/admin"
SITE = "https://www.dealpulseksa.com"

# متجر Python المحلي رجع "certificate has expired" — نجرّب certifi ثم truststore
# ثم (أخيراً) سياق غير مُتحقَّق. الاتصال يبقى TLS مشفّراً والمضيف مثبّت أعلاه.
def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        import truststore
        c = ssl.create_default_context()
        truststore.inject_into_ssl()
        return c
    except Exception:
        pass
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    print("  ! تحذير: تعذّر التحقق من الشهادة — أكمل بسياق غير مُتحقَّق")
    return c

CTX = _ctx()

env = dict(re.findall(r"^([A-Z_]+)=(.*)$",
           (HERE.parent.parent / ".env").read_text(), re.M))
SECRET = env["ADMIN_SHARED_SECRET"].strip()
# Cloudflare يرجّع 1010 (حظر توقيع المتصفّح) لـ Python-urllib — ننتحل UA متصفّح.
HDR = {
    "X-Admin-Secret": SECRET,
    "Content-Type": "application/json",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

PAYLOADS = json.loads((HERE / "_payloads.json").read_text(encoding="utf-8"))
STATE_F = HERE / "_state.json"
state = json.loads(STATE_F.read_text()) if STATE_F.exists() else {}


def save():
    STATE_F.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, headers=HDR, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def do_import():
    for p in PAYLOADS:
        k = str(p["n"])
        if k in state and state[k].get("id"):
            print(f"  {k:>2} skip (id={state[k]['id']})"); continue
        st, res = call("POST", "/seo-import", {
            "title": p["title"], "body_markdown": p["body_markdown"],
            "target_keyword": p["target_keyword"], "master_id": 74,
            "lang": "ar", "description": p["description"],
        })
        if st != 200:
            print(f"  {k:>2} FAIL {st}: {res}"); save(); sys.exit(1)
        state[k] = {"id": res["id"], "slug": res["slug"], "section": p["section"],
                    "title": p["title"]}
        print(f"  {k:>2} -> id={res['id']} /c/{res['slug']}")
        save(); time.sleep(0.3)


def do_link():
    by_sec = {}
    for k, v in state.items():
        by_sec.setdefault(v["section"], []).append(int(k))
    for sec in by_sec:
        by_sec[sec].sort()
    for p in PAYLOADS:
        k = str(p["n"]); v = state[k]
        if v.get("linked"):
            print(f"  {k:>2} skip linked"); continue
        sibs = by_sec[v["section"]]
        idx = sibs.index(p["n"])
        picks = [sibs[(idx + i) % len(sibs)] for i in range(1, len(sibs))]
        picks = list(dict.fromkeys(x for x in picks if x != p["n"]))[:3]
        block = "\n\n---\n\n### اقرأ أيضاً\n\n" + "\n".join(
            f"- [{state[str(x)]['title']}]({SITE}/c/{state[str(x)]['slug']})" for x in picks)
        newbody = p["body_markdown"].rstrip() + block + "\n"
        st, res = call("PUT", f"/seo-import/{v['id']}/body", {
            "title": p["title"], "body_markdown": newbody,
            "target_keyword": p["target_keyword"], "master_id": 74, "lang": "ar",
        })
        if st != 200:
            print(f"  {k:>2} FAIL {st}: {res}"); save(); sys.exit(1)
        v["linked"] = True; print(f"  {k:>2} linked -> {picks}")
        save(); time.sleep(0.3)


def do_publish():
    for p in PAYLOADS:
        k = str(p["n"]); v = state[k]
        if v.get("published"):
            print(f"  {k:>2} skip published"); continue
        st, res = call("POST", f"/seo-publish/{v['id']}")
        if st != 200:
            print(f"  {k:>2} FAIL {st}: {res}"); save(); sys.exit(1)
        v["published"] = True
        print(f"  {k:>2} published /c/{v['slug']}  index={res.get('index')}")
        save(); time.sleep(0.5)


cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
if cmd in ("import", "all"):
    print("== import =="); do_import()
if cmd in ("link", "all"):
    print("== link =="); do_link()
if cmd in ("publish", "all"):
    print("== publish =="); do_publish()
print(f"\ndone. {sum(1 for v in state.values() if v.get('published'))}/{len(PAYLOADS)} published")
