"""يجلب صفحات متجر 74 المنشورة ويكتب قائمة نظيفة UTF-8 + يفحص الربط الداخلي."""
import json, ssl, urllib.request, urllib.parse, pathlib
try:
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    CTX = ssl._create_unverified_context()
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
HERE = pathlib.Path(__file__).parent
OLD = {"كوبون-ناتشورال-تاتش", "كريم-اليدين-ناتشورال-تاتش", "عطور-ناتشورال-تاتش"}


def get(u):
    return json.loads(urllib.request.urlopen(
        urllib.request.Request(u, headers=UA), timeout=30, context=CTX).read())


d = get("https://api.dealpulseksa.com/api/v1/seo/pages?lang=ar&limit=150")
n74 = [p for p in d["pages"] if p["master_id"] == 74]
new = [p for p in n74 if p["slug"] not in OLD]
new.sort(key=lambda p: p.get("published_at") or "")

lines = [f"# روابط ناتشورال تاتش المنشورة — {len(new)} صفحة جديدة (+ {len(n74)-len(new)} قديمة)\n"]
for i, p in enumerate(new, 1):
    lines.append(f"{i}. https://www.dealpulseksa.com/c/{p['slug']}")
    lines.append(f"   {p['title_meta'] or p['target_keyword']}")

# فحص الربط الداخلي على ٣ صفحات عيّنة
lines.append("\n## فحص «اقرأ أيضاً»")
for p in new[:1] + new[len(new)//2:len(new)//2+1] + new[-1:]:
    b = get("https://api.dealpulseksa.com/api/v1/seo/pages/"
            + urllib.parse.quote(p["slug"]))["body_markdown"]
    cnt = b.count("dealpulseksa.com/c/")
    lines.append(f"- {p['slug']}: «اقرأ أيضاً» {'موجود' if 'اقرأ أيضاً' in b else 'مفقود'}"
                 f" — {cnt} رابط داخلي")

(HERE / "_live_urls.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(new)} new pages published. wrote _live_urls.md")
