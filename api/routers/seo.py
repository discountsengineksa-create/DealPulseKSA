"""
SEO landing pages — قراءة عامة (يستهلكها موقع Next.js لعرض الصفحات).

GET /api/v1/seo/pages          — قائمة الصفحات المنشورة (بدون body، خفيف للفهرسة)
GET /api/v1/seo/pages/{slug}   — صفحة منشورة كاملة (مع body_markdown)

التوليد والنشر عبر /api/v1/admin/seo-* (محميّة بـ X-Admin-Secret).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from api.db import get_db

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


class SeoPageList(BaseModel):
    total: int
    pages: list[SeoPageSummary]


@router.get("/pages", response_model=SeoPageList)
def list_pages(
    limit: int = Query(default=100, ge=1, le=500),
    conn=Depends(get_db),
):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT slug, target_keyword, master_id, lang,
                   title_meta, description_meta,
                   to_char(published_at, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS published_at
            FROM seo_landing_pages
            WHERE status = 'published'
            ORDER BY published_at DESC NULLS LAST, id DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return SeoPageList(total=len(rows), pages=[SeoPageSummary(**dict(r)) for r in rows])


@router.get("/pages/{slug}", response_model=SeoPageFull)
def get_page(slug: str, conn=Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT p.slug, p.target_keyword, p.master_id, p.lang,
                   p.title_meta, p.description_meta, p.body_markdown,
                   to_char(p.published_at, 'YYYY-MM-DD"T"HH24:MI:SSZ') AS published_at,
                   m.store_id,
                   COALESCE(NULLIF(m.name_en, ''), m.store_id) AS store_name,
                   m.logo_url, m.discount_value, m.public_coupon, m.cloaked_slug
            FROM seo_landing_pages p
            LEFT JOIN master m ON m.id = p.master_id
            WHERE p.slug = %s AND p.status = 'published'
            """,
            (slug,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="page not found")
    return SeoPageFull(**dict(row))
