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


class SeoPageSummary(BaseModel):
    slug: str
    target_keyword: str
    master_id: int | None = None
    lang: str
    title_meta: str | None = None
    description_meta: str | None = None
    published_at: str | None = None


class SeoPageFull(SeoPageSummary):
    body_markdown: str
    # المتجر المرتبط — لبناء زر العرض (CTA) في صفحة الهبوط
    store_id: str | None = None
    store_name: str | None = None
    logo_url: str | None = None
    discount_value: str | None = None
    public_coupon: str | None = None
    cloaked_slug: str | None = None
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
    where = ["status = 'published'"]
    params: list[Any] = []
    if lang in ("ar", "en"):
        where.append("lang = %s")
        params.append(lang)
    params.append(limit)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""
            SELECT slug, target_keyword, master_id, lang,
                   title_meta, description_meta,
                   to_char(published_at, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS published_at
            FROM seo_landing_pages
            WHERE {' AND '.join(where)}
            ORDER BY published_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            params,
        )
        rows = cur.fetchall()
    return SeoPageList(total=len(rows), pages=[SeoPageSummary(**dict(r)) for r in rows])


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
                   m.logo_url, m.discount_value, m.public_coupon, m.cloaked_slug,
                   m.store_tags
            FROM seo_landing_pages p
            LEFT JOIN master m ON m.id = p.master_id
            WHERE p.slug = %s AND p.status = 'published'
            """,
            (slug,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="page not found")

    page_dict = dict(row)
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
    site_url = os.getenv("SITE_URL", "https://dealpulseksa.com").rstrip("/")
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
