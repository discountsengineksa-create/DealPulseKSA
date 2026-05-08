from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.schemas.coupon import SearchResponse, StoreResult

router = APIRouter(prefix="/coupons", tags=["coupons"])


def _parse_tags(raw: str | None) -> list[str]:
    """تحويل '{tag1,tag2}' → ['tag1', 'tag2'] — نفس منطق dashboard.py."""
    if not raw:
        return []
    s = str(raw).strip().strip("{}").strip()
    return [t.strip() for t in s.split(",") if t.strip()] if s else []


@router.get("/", response_model=SearchResponse)
def get_all_coupons(
    limit: int = Query(default=50, ge=1, le=200),
    conn=Depends(get_db),
):
    """إرجاع جميع المتاجر مرتبةً: الترند أولاً ثم بالمعرّف."""
    sql = """
        SELECT
            id, store_id, name_en, affiliate_link, public_coupon,
            extra_offer, store_bio, store_tags, discount_value,
            total_coupon_copies, total_link_clicks, is_trending,
            0 AS score_pct
        FROM master
        WHERE public_coupon IS NOT NULL AND public_coupon != ''
        ORDER BY
            CASE WHEN is_trending = 'ترند 🔥' THEN 0 ELSE 1 END,
            id ASC
        LIMIT %(limit)s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"limit": limit})
        rows = cur.fetchall()

    results = [
        StoreResult(
            **{k: v for k, v in row.items() if k != "store_tags"},
            store_tags=_parse_tags(row.get("store_tags")),
        )
        for row in rows
    ]
    return SearchResponse(query="", total=len(results), capped=(len(results) == limit), results=results)


@router.get("/search", response_model=SearchResponse)
def search_coupons(
    q: str = Query(..., min_length=2, max_length=100, description="نص البحث"),
    limit: int = Query(default=20, ge=1, le=50),
    conn=Depends(get_db),
):
    """
    البحث الذكي بالـ Trigram Similarity.
    - يستخدم فهارس pg_trgm تلقائياً عبر ILIKE
    - يُرتّب النتائج بدرجة التشابه (الأدق أولاً)
    - يدعم البحث الجزئي: 'نمش' تُعيد 'نمشي'
    """
    _like = f"%{q}%"

    sql = """
        WITH filtered AS (
            SELECT
                id, store_id, name_en, affiliate_link, public_coupon,
                extra_offer, store_bio, store_tags, discount_value,
                total_coupon_copies, total_link_clicks, is_trending,
                GREATEST(
                    similarity(lower(store_id),                lower(%(term)s)),
                    similarity(lower(COALESCE(name_en,   '')), lower(%(term)s)),
                    similarity(lower(COALESCE(store_tags,'')), lower(%(term)s))
                ) AS relevance_score
            FROM master
            WHERE
                store_id               ILIKE %(like)s
                OR COALESCE(name_en,   '') ILIKE %(like)s
                OR COALESCE(store_tags,'') ILIKE %(like)s
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
            **{k: v for k, v in row.items() if k != "store_tags"},
            store_tags=_parse_tags(row.get("store_tags")),
        )
        for row in rows
    ]

    return SearchResponse(
        query=q,
        total=len(results),
        capped=(len(results) == limit),
        results=results,
    )
