"""
SEO landing pages — قراءة عامة (يستهلكها موقع Next.js لعرض الصفحات).

GET /api/v1/seo/pages           — قائمة الصفحات المنشورة (بدون body، خفيف)
GET /api/v1/seo/pages/{slug}    — صفحة منشورة كاملة (body + JSON-LD structured data)

التوليد والنشر عبر /api/v1/admin/seo-* (محميّة بـ X-Admin-Secret).

JSON-LD: كل صفحة كاملة تأتي بـ structured data تشمل Article + Offer +
Organization + BreadcrumbList + FAQPage (لو في أسئلة). يضع Next.js هذا في
<script type="application/ld+json"> لتظهر في Google Rich Results + AI Overviews
+ يُقتبس بواسطة ChatGPT/Gemini/Perplexity.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from api.db import get_db
from api.seo.schema_markup import build_jsonld

router = APIRouter(prefix="/seo", tags=["seo"])

# ── الكود المنتهي لا يُعرض — ولا حتى داخل متن صفحة /c/ ──────────────────────
# صفحات الهبوط تُولَّد مرّة ويُطبع الكود **نصّاً ثابتاً** في `body_markdown`
# و`description_meta`، فحين ينتهي العرض تبقى تنشر كوداً ميّتاً بينما بقيّة
# المنصّة أخفته (الموقع/البوت/الميني). الحجب عند التقديم لا في القاعدة:
# لا نفقد المحتوى، ويرجع الكود وحده لحظة تمديد `last_time`.
_OFFER_ACTIVE_SQL = "(m.last_time IS NULL OR m.last_time > CURRENT_DATE)"


def _tags_arr(alias: str) -> str:
    """store_tags نصّ بصيغة '{a,b,c}' (ليس text[]) — نحوّله لـ text[] نظيف."""
    return (
        "ARRAY(SELECT trim(t) FROM unnest(string_to_array("
        f"trim(both '{{}}' from COALESCE({alias}.store_tags, '')), ',')) AS t "
        "WHERE trim(t) <> '')"
    )


# متاجر بنفس التصنيف (تقاطع store_tags) + كوبون فعّال — الأشهر أولاً
_RELATED_STORES_SQL = f"""
    WITH me AS (SELECT {_tags_arr('m0')} AS tags FROM master m0 WHERE m0.id = %s)
    SELECT m.store_id,
           COALESCE(NULLIF(m.name_en, ''), m.store_id) AS store_name,
           m.logo_url, m.cloaked_slug, m.discount_value, m.public_coupon
    FROM master m, me
    WHERE m.id <> %s
      AND COALESCE(m.seo_enabled, TRUE)
      AND {_OFFER_ACTIVE_SQL}
      AND m.public_coupon IS NOT NULL AND m.public_coupon <> ''
      AND cardinality(me.tags) > 0
      AND {_tags_arr('m')} && me.tags
    ORDER BY (COALESCE(m.total_link_clicks, 0)
              + COALESCE(m.total_coupon_copies, 0)) DESC, m.store_id
    LIMIT 10
"""


def _strip_dead_code(body: str | None, code: str | None) -> str | None:
    """يُسقط كل سطر يذكر الكود المنتهي من متن الصفحة (بقيّة الدليل تبقى)."""
    if not body or not code:
        return body
    return "\n".join(ln for ln in body.splitlines() if code not in ln)


def _clean_meta(desc: str | None, code: str | None, keyword: str, lang: str = "ar") -> str | None:
    """الوصف سطر واحد — لو حمل الكود المنتهي نستبدله بوصف عام بلا ادّعاء."""
    if not desc or not code or code not in desc:
        return desc
    if lang == "en":
        return f"{keyword} — latest offers and deals with Deal Pulse KSA."
    return f"{keyword} — أحدث العروض والتخفيضات مع نبض الصفقات."


class SeoPageSummary(BaseModel):
    slug: str
    target_keyword: str
    master_id: int | None = None
    lang: str
    title_meta: str | None = None
    description_meta: str | None = None
    published_at: str | None = None


class RelatedStore(BaseModel):
    store_id: str | None = None
    store_name: str | None = None
    logo_url: str | None = None
    cloaked_slug: str | None = None
    discount_value: str | None = None
    public_coupon: str | None = None


class SeoPageFull(SeoPageSummary):
    body_markdown: str
    # المتجر المرتبط — لبناء زر العرض (CTA) في صفحة الهبوط
    store_id: str | None = None
    store_name: str | None = None
    logo_url: str | None = None
    discount_value: str | None = None
    public_coupon: str | None = None
    cloaked_slug: str | None = None
    # متاجر بنفس التصنيف (store_tags) بأكوادها — تُعرض نهاية كل صفحة /c/
    related_stores: list[RelatedStore] = []
    # JSON-LD structured data — يضعه Next.js في <script type="application/ld+json">
    jsonld: dict[str, Any] | None = None


class SeoPageList(BaseModel):
    total: int
    pages: list[SeoPageSummary]


@router.get("/pages", response_model=SeoPageList)
def list_pages(
    limit: int = Query(default=100, ge=1, le=500),
    lang: str | None = Query(default=None, description="ar / en — اختياري للتصفية"),
    conn=Depends(get_db),
):
    """قائمة الصفحات المنشورة (للـ sitemap + الفهرسة الذاتية)."""
    where = ["p.status = 'published'"]
    params: list[Any] = []
    if lang in ("ar", "en"):
        where.append("p.lang = %s")
        params.append(lang)
    params.append(limit)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT p.slug, p.target_keyword, p.master_id, p.lang,
                   p.title_meta, p.description_meta,
                   to_char(p.published_at, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS published_at,
                   CASE WHEN {_OFFER_ACTIVE_SQL} THEN NULL ELSE m.public_coupon END AS dead_code
            FROM seo_landing_pages p
            LEFT JOIN master m ON m.id = p.master_id
            WHERE {' AND '.join(where)}
            ORDER BY p.published_at DESC NULLS LAST, p.id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()

    pages = []
    for r in rows:
        d = dict(r)
        dead = d.pop("dead_code", None)
        d["description_meta"] = _clean_meta(
            d["description_meta"], dead, d["target_keyword"], d.get("lang") or "ar"
        )
        pages.append(SeoPageSummary(**d))
    return SeoPageList(total=len(pages), pages=pages)


@router.get("/pages/{slug}", response_model=SeoPageFull)
def get_page(slug: str, conn=Depends(get_db)):
    """
    صفحة منشورة كاملة. يتضمّن الرد:
      • body_markdown + meta للعرض
      • jsonld: structured data جاهز لإدراجه في الصفحة
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.slug, p.target_keyword, p.master_id, p.lang,
                   p.title_meta, p.description_meta, p.body_markdown,
                   to_char(p.published_at, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS published_at,
                   m.store_id,
                   COALESCE(NULLIF(m.name_en, ''), m.store_id) AS store_name,
                   m.logo_url, m.cloaked_slug, m.store_tags,
                   CASE WHEN {active} THEN m.discount_value END AS discount_value,
                   CASE WHEN {active} THEN m.public_coupon  END AS public_coupon,
                   CASE WHEN {active} THEN NULL ELSE m.public_coupon END AS dead_code
            FROM seo_landing_pages p
            LEFT JOIN master m ON m.id = p.master_id
            WHERE p.slug = %s AND p.status = 'published'
            """.format(active=_OFFER_ACTIVE_SQL),
            (slug,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="page not found")

    page_dict = dict(row)
    # العرض منتهٍ ⇒ يُمحى الكود من المتن والوصف قبل بناء JSON-LD، وإلا سرّبه
    # الـstructured data إلى Google وإلى محرّكات الـAI بعد موته.
    dead_code = page_dict.pop("dead_code", None)
    if dead_code:
        page_dict["body_markdown"] = _strip_dead_code(page_dict["body_markdown"], dead_code)
        page_dict["description_meta"] = _clean_meta(
            page_dict.get("description_meta"), dead_code, page_dict["target_keyword"],
            page_dict.get("lang") or "ar",
        )
    # متاجر بنفس التصنيف بأكوادها (فارغة لو المتجر بلا store_tags)
    related_stores: list[RelatedStore] = []
    if page_dict.get("master_id"):
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(_RELATED_STORES_SQL,
                        (page_dict["master_id"], page_dict["master_id"]))
            related_stores = [RelatedStore(**dict(r)) for r in cur.fetchall()]

    # نبني JSON-LD ونضمّنه في الرد (Next.js يلصقه في <head>)
    jsonld = build_jsonld(page_dict)

    return SeoPageFull(
        slug=page_dict["slug"],
        target_keyword=page_dict["target_keyword"],
        master_id=page_dict.get("master_id"),
        lang=page_dict.get("lang") or "ar",
        title_meta=page_dict.get("title_meta"),
        description_meta=page_dict.get("description_meta"),
        published_at=page_dict.get("published_at"),
        body_markdown=page_dict["body_markdown"],
        store_id=page_dict.get("store_id"),
        store_name=page_dict.get("store_name"),
        logo_url=page_dict.get("logo_url"),
        discount_value=page_dict.get("discount_value"),
        public_coupon=page_dict.get("public_coupon"),
        cloaked_slug=page_dict.get("cloaked_slug"),
        related_stores=related_stores,
        jsonld=jsonld,
    )


@router.get("/sitemap.xml")
def sitemap_xml(conn=Depends(get_db)):
    """
    sitemap XML لكل الصفحات المنشورة. Google/Bing يقرأون هذا.
    Next.js يفترض أن يُعيد توجيه /sitemap.xml إلى هذا الـ endpoint.
    """
    from fastapi.responses import Response
    import os
    site_url = os.getenv("SITE_URL", "https://www.dealpulseksa.com").rstrip("/")
    page_path_tpl = os.getenv("SEO_PAGE_PATH", "/c/{slug}")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT slug, lang,
                   to_char(COALESCE(published_at, NOW()), 'YYYY-MM-DD') AS lastmod
            FROM seo_landing_pages
            WHERE status = 'published'
            ORDER BY published_at DESC NULLS LAST
            LIMIT 50000
            """,
        )
        rows = cur.fetchall()

    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemap.org/schemas/sitemap/0.9" '
             'xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    # Homepage
    parts.append(f'<url><loc>{site_url}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>')

    for slug, lang, lastmod in rows:
        url = f"{site_url}{page_path_tpl.format(slug=slug)}"
        parts.append(
            f'<url><loc>{url}</loc>'
            f'<lastmod>{lastmod}</lastmod>'
            f'<changefreq>weekly</changefreq>'
            f'<priority>0.8</priority>'
            f'</url>'
        )
    parts.append('</urlset>')
    xml = "\n".join(parts)
    return Response(content=xml, media_type="application/xml")
