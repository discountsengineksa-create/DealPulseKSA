from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from api.db import get_db
from api.schemas.coupon import SearchResponse, StoreResult

router = APIRouter(prefix="/coupons", tags=["coupons"])


class CategoryItem(BaseModel):
    tag_name:      str
    priority_rank: int
    click_count:   int


class CategoriesResponse(BaseModel):
    categories: list[CategoryItem]


def _parse_tags(raw: str | None) -> list[str]:
    """تحويل '{tag1,tag2}' → ['tag1', 'tag2'] — نفس منطق dashboard.py."""
    if not raw:
        return []
    s = str(raw).strip().strip("{}").strip()
    return [t.strip() for t in s.split(",") if t.strip()] if s else []


def _select_lang_clause(lang: str) -> str:
    """
    يبني SELECT يحقن قيم اللغة المطلوبة في الحقول الأساسية،
    ويُرجع نسخ EN raw كأعمدة مرافقة (مفيد لعرض الـ admin بكلتا اللغتين).
    Fallback تلقائي للعربيّة إذا كانت قيم EN فارغة.
    """
    if lang == "en":
        return """
            id,
            store_id,
            -- name_en للعرض بالإنجليزية. لا نُبدّل store_id بالاسم الإنجليزي:
            -- store_id هو المفتاح الأساسي (للمفضلة/التتبّع/الربط) ويجب أن يبقى
            -- ثابتاً عبر اللغتين. الواجهة تعرض name_en وتستخدم store_id للعمليات.
            COALESCE(NULLIF(name_en, ''), store_id) AS name_en,
            affiliate_link, public_coupon,
            COALESCE(NULLIF(extra_offer_en, ''), extra_offer)   AS extra_offer,
            extra_offer_en,
            COALESCE(NULLIF(store_bio_en, ''),   store_bio)     AS store_bio,
            store_bio_en,
            description,
            COALESCE(NULLIF(store_tags_en, ''),  store_tags)    AS store_tags,
            store_tags_en,
            discount_value,
            total_coupon_copies, total_link_clicks, is_trending,
            COALESCE(is_promoted, FALSE) AS is_promoted,
            logo_url, cloaked_slug
        """
    return """
        id, store_id, name_en, affiliate_link, public_coupon,
        extra_offer, extra_offer_en,
        store_bio,   store_bio_en,
        description,
        store_tags,  store_tags_en,
        discount_value,
        total_coupon_copies, total_link_clicks, is_trending,
        COALESCE(is_promoted, FALSE) AS is_promoted,
        logo_url, cloaked_slug
    """


@router.get("/categories", response_model=CategoriesResponse)
def get_categories(conn=Depends(get_db)):
    """
    يُعيد قائمة الأقسام مرتبةً بـ priority_rank ASC ثم النقرات DESC.
    أقسام بدون rank تحصل على الافتراضي 5 ولا تُحدث crash.
    """
    sql = """
        WITH tags_raw AS (
            SELECT DISTINCT trim(tg) AS tag
            FROM master,
                 unnest(string_to_array(
                     trim(both '{}' from COALESCE(store_tags, '')), ','
                 )) AS tg
            WHERE trim(tg) <> ''
              AND (last_time IS NULL OR last_time >= CURRENT_DATE)
        )
        SELECT
            t.tag                                  AS tag_name,
            COALESCE(ct.priority_rank,    5)       AS priority_rank,
            COALESCE(ct."Tag_clicks",     0)       AS click_count
        FROM tags_raw t
        LEFT JOIN categories_tags ct ON ct.tag_name = t.tag
        ORDER BY
            COALESCE(ct.priority_rank, 5)  ASC,
            COALESCE(ct."Tag_clicks",  0)  DESC,
            t.tag                          ASC
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return CategoriesResponse(categories=[CategoryItem(**dict(r)) for r in rows])


@router.get("/", response_model=SearchResponse)
def get_all_coupons(
    limit: int = Query(default=50, ge=1, le=1000),     # رفع السقف من 200 لـ 1000
    lang: Literal["ar", "en"] = Query(default="ar"),
    conn=Depends(get_db),
):
    """إرجاع جميع المتاجر مرتبةً: الترند أولاً ثم بالمعرّف. ?lang=en يبدّل الحقول للإنجليزية."""
    sql = f"""
        SELECT
            {_select_lang_clause(lang)},
            0 AS score_pct
        FROM master
        WHERE (last_time IS NULL OR last_time >= CURRENT_DATE)
        ORDER BY
            CASE WHEN COALESCE(is_promoted, FALSE) THEN 0 ELSE 1 END,
            CASE WHEN is_trending = 'ترند 🔥'      THEN 0 ELSE 1 END,
            id ASC
        LIMIT %(limit)s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"limit": limit})
        rows = cur.fetchall()

    results = [
        StoreResult(
            **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en")},
            store_tags=_parse_tags(row.get("store_tags")),
            store_tags_en=_parse_tags(row.get("store_tags_en")),
        )
        for row in rows
    ]
    return SearchResponse(query="", total=len(results), capped=(len(results) == limit), results=results)


@router.get("/search", response_model=SearchResponse)
def search_coupons(
    q: str = Query(..., min_length=2, max_length=100, description="نص البحث"),
    limit: int = Query(default=20, ge=1, le=50),
    lang: Literal["ar", "en"] = Query(default="ar"),
    conn=Depends(get_db),
):
    """
    البحث الذكي بالـ Trigram Similarity.
    - يبحث في الحقول العربيّة والإنجليزيّة معاً (المستخدم قد يكتب بأيّ لغة).
    - ?lang=en يبدّل قيم الاستجابة للإنجليزيّة (Fallback للعربية إذا فارغة).
    """
    _like = f"%{q}%"

    sql = f"""
        WITH filtered AS (
            SELECT
                {_select_lang_clause(lang)},
                GREATEST(
                    similarity(lower(store_id),                    lower(%(term)s)),
                    similarity(lower(COALESCE(name_en,        '')), lower(%(term)s)),
                    similarity(lower(COALESCE(store_tags,     '')), lower(%(term)s)),
                    similarity(lower(COALESCE(store_tags_en,  '')), lower(%(term)s)),
                    similarity(lower(COALESCE(store_bio_en,   '')), lower(%(term)s))
                ) AS relevance_score
            FROM master
            WHERE
                (last_time IS NULL OR last_time >= CURRENT_DATE)
                AND (
                    store_id                       ILIKE %(like)s
                    OR COALESCE(name_en,       '') ILIKE %(like)s
                    OR COALESCE(store_tags,    '') ILIKE %(like)s
                    OR COALESCE(store_tags_en, '') ILIKE %(like)s
                    OR COALESCE(store_bio_en,  '') ILIKE %(like)s
                )
        )
        SELECT *, (relevance_score * 100)::int AS score_pct
        FROM filtered
        WHERE relevance_score > 0.05
        ORDER BY relevance_score DESC
        LIMIT %(limit)s
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"term": q, "like": _like, "limit": limit})
        rows = cur.fetchall()

    results = [
        StoreResult(
            **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en")},
            store_tags=_parse_tags(row.get("store_tags")),
            store_tags_en=_parse_tags(row.get("store_tags_en")),
        )
        for row in rows
    ]

    return SearchResponse(
        query=q,
        total=len(results),
        capped=(len(results) == limit),
        results=results,
    )
