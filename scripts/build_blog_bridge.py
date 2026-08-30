"""
جسر المدوّنة: يقرأ lib/blog.ts (ريبو الويب) ويبني جدول blog_bridge —
**صفّ واحد لكل مقال** موضوعه ضيّق: نصّه المطبّع + المتاجر التي يذكرها.

المشكلة التي يحلّها (طلب المالك، 2026-08-30):
  «لو كتب فحمات بعد ما قرا مقال الفحمات — تشوف الكلمة وين انكتبت، بعدين
   تعطيني المتاجر المرتبطة بهذا المقال.»

  الطبقة المنتقاة (search_concepts) تحلّ القسم؛ هذه الطبقة **احتياط أخير**:
  حين لا يُطابق الاستعلامُ اسمَ متجر ولا مفهوماً، نبحث في نصوص المقالات ضيّقة
  الموضوع (Postgres FTS, بترتيب ts_rank)، ونُرجع متاجر أعلى ١–٣ مقالات مع
  عنوان المقال في `via_article`.

لماذا صفّ/مقال لا صفّ/كلمة: فهرسة الكلمات أنتجت ٩٤ ألف صفّ و٤٠ ألف «كلمة» —
  فهرس نصّي كامل بجودة رديئة لا جسراً. صفّ/مقال = ١٬٤٠٠ صفّ، وترتيب FTS
  يتكفّل بالصلة.

لماذا Python لا سكربت في ريبو الويب: blog.ts ~6MB يُفجّر tsc؛ نقرؤه نصّاً.
  وريبو الويب بلا اعتماد pg.

الاستخدام:
    python -m scripts.build_blog_bridge                 # dry-run: إحصاء + JSON معاينة
    python -m scripts.build_blog_bridge --write         # upsert (يحتاج migration_070 + إذن المالك)
    python -m scripts.build_blog_bridge --blog PATH

⚠️ --write كتابة DB على الإنتاج — لا تشغّلها بلا إذن المالك للعملية بعينها.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from urllib.parse import unquote

from api.utils.arabic_search import normalize_ar

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
_BLOG_CANDIDATES = [
    REPO.parent / "dealpulseksa-web" / "lib" / "blog.ts",
    pathlib.Path("C:/Users/PC/Desktop/dealpulseksa-web/lib/blog.ts"),
]

# ── ضبط ──────────────────────────────────────────────────────────────────────
# فلسفة: هذا الجسر احتياط أخير — نُبقي المقالات ضيّقة الموضوع فقط، فمقال يعدّد
# عشرة متاجر «أفضل متاجر س» يخدمه المفهوم لا الجسر.
MIN_STORES = 1
MAX_STORES = 6                 # أكثر = فهرس/مقارنة لا موضوع
BODY_CHARS = 5000              # يكفي FTS، ويُبقي الجدول صغيراً

_POST_SPLIT = re.compile(r"\n(?=[ \t]*\{[ \t]*\n[ \t]*slug:[ \t]*')")
_SLUG = re.compile(r"slug:\s*'([^']+)'")
_TITLE = re.compile(r"\btitle:\s*'((?:[^'\\]|\\.)*)'")
_CATEGORY = re.compile(r"\bcategory:\s*'([^']*)'")
_EXCERPT = re.compile(r"\bexcerpt:\s*'((?:[^'\\]|\\.)*)'")
_BODY = re.compile(r"\bbody:\s*`([^`]*)`", re.DOTALL)   # المتن (بلا ` داخله بحكم SWC)
_STORE_LINK = re.compile(r"/store/([^)\"'\s?#]+)")
_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")          # [نص](رابط) → نص
_URL = re.compile(r"https?://\S+")
_NOISE = re.compile(r"[`*_>#|~\[\]()]+")


def _find_blog(explicit: str | None) -> pathlib.Path:
    if explicit:
        p = pathlib.Path(explicit)
        if p.is_file():
            return p
        sys.exit(f"blog.ts غير موجود: {p}")
    for c in _BLOG_CANDIDATES:
        if c.is_file():
            return c
    sys.exit("لم أجد lib/blog.ts — مرّر --blog PATH")


def _decode_store(raw: str) -> str:
    return unquote(raw.replace("+", " ")).strip()


def _clean(text: str) -> str:
    text = _MD_LINK.sub(r" \1 ", text)
    text = _URL.sub(" ", text)
    text = _NOISE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_posts(text: str) -> list[dict]:
    posts: list[dict] = []
    for chunk in _POST_SPLIT.split(text)[1:]:
        m = _SLUG.search(chunk)
        if not m:
            continue
        slug = m.group(1)
        body_m = _BODY.search(chunk)
        body = body_m.group(1) if body_m else ""
        title_m, exc_m, cat_m = (
            _TITLE.search(chunk), _EXCERPT.search(chunk), _CATEGORY.search(chunk),
        )
        title = (title_m.group(1) if title_m else slug).replace("\\'", "'")
        excerpt = (exc_m.group(1) if exc_m else "").replace("\\'", "'")
        # روابط المتاجر من المتن وحده (لا body_en).
        store_ids = sorted({_decode_store(s) for s in _STORE_LINK.findall(body)})
        blob = _clean(" ".join((title, excerpt, body)))
        posts.append({
            "slug": slug,
            "title": _clean(title),
            "category": cat_m.group(1) if cat_m else "",
            "store_ids": store_ids,
            "body_norm": normalize_ar(blob)[:BODY_CHARS],
        })
    return posts


def build(blog_path: pathlib.Path) -> tuple[list[dict], dict]:
    posts = parse_posts(blog_path.read_text(encoding="utf-8"))
    rows = [
        p for p in posts
        if MIN_STORES <= len(p["store_ids"]) <= MAX_STORES and p["body_norm"]
    ]
    stats = {
        "blog_file": str(blog_path),
        "posts_total": len(posts),
        "bridge_rows": len(rows),
        "skipped_no_store": sum(1 for p in posts if not p["store_ids"]),
        "skipped_too_many_stores": sum(1 for p in posts if len(p["store_ids"]) > MAX_STORES),
        "avg_body_chars": round(sum(len(p["body_norm"]) for p in rows) / max(len(rows), 1)),
        "distinct_stores_linked": len({s for p in rows for s in p["store_ids"]}),
    }
    return rows, stats


def write_db(rows: list[dict]) -> None:
    import os

    import psycopg2
    from dotenv import load_dotenv
    from psycopg2.extras import execute_batch

    load_dotenv(str(REPO / ".env"))
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        sys.exit("DATABASE_URL غير مضبوط في .env")
    conn = psycopg2.connect(dsn)
    with conn, conn.cursor() as cur:
        cur.execute("SELECT to_regclass('blog_bridge')")
        if cur.fetchone()[0] is None:
            sys.exit("جدول blog_bridge غير موجود — شغّل migration_070_search_intelligence.sql أولاً")
        # الجدول مشتقّ بالكامل من blog.ts — استبدال كامل، فالصفّ القديم بيانات بايتة.
        cur.execute("TRUNCATE blog_bridge")
        execute_batch(cur, """
            INSERT INTO blog_bridge (slug, title, category, store_ids, body_norm, updated_at)
            VALUES (%(slug)s, %(title)s, %(category)s,
                    %(store_ids_sql)s, %(body_norm)s, now())
        """, [
            {**r, "store_ids_sql": "{" + ",".join(r["store_ids"]) + "}"}
            for r in rows
        ])
    print(f"✓ blog_bridge: {len(rows)} صفّ (صفّ/مقال).")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--blog")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows, stats = build(_find_blog(args.blog))
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    DATA.mkdir(exist_ok=True)
    out = DATA / "blog_bridge_preview.json"
    out.write_text(json.dumps(
        [{"slug": r["slug"], "title": r["title"], "category": r["category"],
          "store_ids": r["store_ids"], "body_norm": r["body_norm"][:220] + "…"}
         for r in rows[:200]],
        ensure_ascii=False, indent=1,
    ), encoding="utf-8")
    print(f"\nمعاينة أول 200 مقال → {out}")

    if args.write:
        write_db(rows)
    else:
        print("\n(dry-run) — أضِف --write بعد مراجعة المعاينة وإذن المالك.")


if __name__ == "__main__":
    main()
