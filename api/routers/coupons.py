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


@router.get("/top-favorited")
def get_top_favorited_stores(
    limit: int = Query(default=10, ge=1, le=20),
    conn=Depends(get_db),
):
    """أبرز المتاجر = أكثر المتاجر تفضيلاً عبر القنوات الثلاث (bot+miniapp+web).
    يُستخدم في الصف الأفقي تحت الستوري على الموقع/الميني. الترتيب من الأكثر
    تفضيلاً تنازلياً؛ المتاجر المنتهية/المعلَّقة مُستثناة.
    """
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                WITH fav_counts AS (
                    SELECT store_id, COUNT(*) AS fav_count
                    FROM user_favorites
                    WHERE COALESCE(kind, 'store') = 'store'
                      AND store_id IS NOT NULL
                    GROUP BY store_id
                )
                SELECT m.store_id,
                       COALESCE(NULLIF(m.name_en, ''), m.store_id) AS name_en,
                       m.logo_url, m.affiliate_link, m.public_coupon,
                       m.discount_value,
                       COALESCE(NULLIF(m.extra_offer_en, ''), m.extra_offer) AS extra_offer,
                       m.extra_offer_en,
                       m.cloaked_slug,
                       fc.fav_count
                FROM master m
                JOIN fav_counts fc ON fc.store_id = m.store_id
                WHERE (m.last_time IS NULL OR m.last_time >= CURRENT_DATE)
                  AND NOT COALESCE(m.is_suspended, FALSE)
                ORDER BY fc.fav_count DESC, m.store_id ASC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return {"stores": [dict(r) for r in rows]}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"stores": []}


@router.get("/site-theme")
def get_site_theme(conn=Depends(get_db)):
    """الثيم الفعّال + إعدادات الشفافية لخلفية الموقع/الميني-ويب (عام، بلا مصادقة).
    يُرجع {"theme": {...} | null, "visual": {overlay_opacity, card_opacity,
    icon_opacity, blur_px}}. الـvisual يُستخدم حتى لو الـtheme=null."""
    theme_row = None
    visual = {"overlay_opacity": 0.35, "card_opacity": 0.42,
              "icon_opacity": 0.55, "blur_px": 28}
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, desktop_url, mobile_url, "
                "desktop_dark_url, mobile_dark_url "
                "FROM site_themes WHERE is_active LIMIT 1"
            )
            theme_row = cur.fetchone()
            # إعدادات الشفافية (singleton). لو الجدول/الصف غير موجودَين نستعمل الافتراضي.
            try:
                cur.execute(
                    "SELECT overlay_opacity, card_opacity, icon_opacity, blur_px "
                    "FROM site_visual_settings WHERE id=1"
                )
                vrow = cur.fetchone()
                if vrow:
                    visual = {
                        "overlay_opacity": float(vrow["overlay_opacity"]),
                        "card_opacity":    float(vrow["card_opacity"]),
                        "icon_opacity":    float(vrow["icon_opacity"]),
                        "blur_px":         int(vrow["blur_px"]),
                    }
            except Exception:
                conn.rollback()
        return {"theme": dict(theme_row) if theme_row else None, "visual": visual}
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return {"theme": None, "visual": visual}


# «الأكثر طلباً» = نقرات الرابط + نسخ الكوبون + عدد مرات البحث عن المتجر +
# عدد المُفضِّلين له. النقرات/النسخ عدّادات في master؛ البحث من action_logs
# (action_type='search')؛ المفضّلة من user_favorites (kind='store').
# subqueries عدديّة مرتبطة — لا تُحدِث التباس أعمدة مع master، ورخيصة (عدد
# المتاجر صغير + الاستجابة مُخزّنة 60 ثانية على الواجهة).
_POPULARITY_SQL = """
    (
        COALESCE(total_link_clicks, 0)
      + COALESCE(total_coupon_copies, 0)
      + (SELECT COUNT(*) FROM action_logs al
            WHERE al.action_type = 'search' AND al.store_id = master.store_id)
      + (SELECT COUNT(*) FROM user_favorites uf
            WHERE uf.kind = 'store' AND uf.store_id = master.store_id)
    )::int AS popularity_score
"""


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
            logo_url, cloaked_slug, story_ring_color,
            COALESCE((SELECT array_agg(ss.media_url ORDER BY ss.sort_order, ss.id)
                      FROM story_slides ss
                      WHERE ss.master_id = master.id AND ss.is_active
                        AND (ss.expires_at IS NULL OR ss.expires_at > now())),
                     ARRAY[]::text[]) AS story_slides,
            COALESCE((SELECT json_agg(json_build_object(
                        'public_coupon',  ec.public_coupon,
                        'discount_value', ec.discount_value,
                        'extra_offer',    ec.extra_offer,
                        'extra_offer_en', ec.extra_offer_en
                      ) ORDER BY ec.sort_order, ec.id)
                      FROM store_extra_coupons ec
                      WHERE ec.master_id = master.id AND ec.is_active
                        AND (ec.start_date IS NULL OR ec.start_date <= CURRENT_DATE)
                        AND (ec.end_date   IS NULL OR ec.end_date   >= CURRENT_DATE)),
                     '[]'::json) AS extra_coupons
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
        logo_url, cloaked_slug, story_ring_color,
        COALESCE((SELECT array_agg(ss.media_url ORDER BY ss.sort_order, ss.id)
                  FROM story_slides ss
                  WHERE ss.master_id = master.id AND ss.is_active
                    AND (ss.expires_at IS NULL OR ss.expires_at > now())),
                 ARRAY[]::text[]) AS story_slides,
        COALESCE((SELECT json_agg(json_build_object(
                    'public_coupon',  ec.public_coupon,
                    'discount_value', ec.discount_value,
                    'extra_offer',    ec.extra_offer,
                    'extra_offer_en', ec.extra_offer_en
                  ) ORDER BY ec.sort_order, ec.id)
                  FROM store_extra_coupons ec
                  WHERE ec.master_id = master.id AND ec.is_active
                    AND (ec.start_date IS NULL OR ec.start_date <= CURRENT_DATE)
                    AND (ec.end_date   IS NULL OR ec.end_date   >= CURRENT_DATE)),
                 '[]'::json) AS extra_coupons
    """


def _select_light_clause(lang: str) -> str:
    """SELECT خفيف للقائمة الكاملة (آلاف المتاجر): اسم/لوقو/خصم/تاغات/عدّادات فقط.
    بلا subqueries (ستوري/أكواد إضافية/وصف) وبلا popularity — فيبقى مسحاً سريعاً
    لجدول master يتحمّل 3000+ متجراً. التفاصيل الكاملة تُجلب لكل متجر عبر /detail."""
    if lang == "en":
        return """
            id, store_id,
            COALESCE(NULLIF(name_en, ''), store_id)              AS name_en,
            COALESCE(NULLIF(extra_offer_en, ''), extra_offer)    AS extra_offer,
            COALESCE(NULLIF(store_tags_en, ''),  store_tags)     AS store_tags,
            discount_value, is_trending,
            COALESCE(is_promoted, FALSE) AS is_promoted,
            logo_url, total_coupon_copies, total_link_clicks
        """
    return """
        id, store_id, name_en, extra_offer, store_tags,
        discount_value, is_trending,
        COALESCE(is_promoted, FALSE) AS is_promoted,
        logo_url, total_coupon_copies, total_link_clicks
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
              AND NOT COALESCE(is_suspended, FALSE)
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
    limit: int = Query(default=50, ge=1, le=5000),     # light يسمح حتى 5000 (كتالوج كامل)
    lang: Literal["ar", "en"] = Query(default="ar"),
    view: Literal["full", "light"] = Query(default="full"),
    conn=Depends(get_db),
):
    """إرجاع المتاجر مرتبةً: المروّجة ثم الترند ثم بالمعرّف. ?lang=en يبدّل الحقول.
    ?view=light → قائمة خفيفة سريعة (بلا ستوري/أكواد إضافية/وصف/popularity) للكتالوج
    الكامل (آلاف المتاجر)؛ التفاصيل تُجلب لكل متجر عبر /coupons/detail/{id}."""
    if view == "light":
        select_clause = _select_light_clause(lang)
        pop_clause = "0 AS popularity_score"
    else:
        select_clause = _select_lang_clause(lang)
        pop_clause = _POPULARITY_SQL
    sql = f"""
        SELECT
            {select_clause},
            {pop_clause},
            0 AS score_pct
        FROM master
        WHERE (last_time IS NULL OR last_time >= CURRENT_DATE)
              AND NOT COALESCE(is_suspended, FALSE)
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
    # نُطبّع المسافات: المستخدم قد يكتب «ترنديول» والمتجر «ترند يول».
    # ILIKE العادي يفشل في هذه الحالة — نطبّق REPLACE على الجانبين.
    _q_no_ws = "".join(q.split())            # "ترنديول"
    _like_no_ws = f"%{_q_no_ws}%"

    sql = f"""
        WITH filtered AS (
            SELECT
                {_select_lang_clause(lang)},
                {_POPULARITY_SQL},
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
              AND NOT COALESCE(is_suspended, FALSE)
                AND (
                    store_id                       ILIKE %(like)s
                    OR COALESCE(name_en,       '') ILIKE %(like)s
                    OR COALESCE(store_tags,    '') ILIKE %(like)s
                    OR COALESCE(store_tags_en, '') ILIKE %(like)s
                    OR COALESCE(store_bio_en,  '') ILIKE %(like)s
                    -- مطابقة بدون مسافات: «ترنديول» يطابق «ترند يول»
                    OR REPLACE(store_id,                       ' ', '') ILIKE %(like_no_ws)s
                    OR REPLACE(COALESCE(name_en,       ''),    ' ', '') ILIKE %(like_no_ws)s
                    OR REPLACE(COALESCE(store_tags,    ''),    ' ', '') ILIKE %(like_no_ws)s
                    OR REPLACE(COALESCE(store_tags_en, ''),    ' ', '') ILIKE %(like_no_ws)s
                )
        )
        SELECT *, (relevance_score * 100)::int AS score_pct
        FROM filtered
        WHERE relevance_score > 0.05
        ORDER BY relevance_score DESC
        LIMIT %(limit)s
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"term": q, "like": _like,
                          "like_no_ws": _like_no_ws, "limit": limit})
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


# مسار التفاصيل الكاملة لمتجر واحد (كوبون/وصف/ستوري/أكواد إضافية) — يُكمّل القائمة
# الخفيفة (?view=light). مُسجَّل في نهاية الملف ليفوز المسار الثابت (search/categories/
# site-theme) في المطابقة قبل بارامتر المسار. /detail/{id} مقطعان فلا التباس.
@router.get("/detail/{store_pk}", response_model=StoreResult)
def get_coupon_detail(
    store_pk: int,
    lang: Literal["ar", "en"] = Query(default="ar"),
    conn=Depends(get_db),
):
    """التفاصيل الكاملة لمتجر بمعرّفه الرقمي (id)؛ يخدم «التفاصيل عند الطلب» للميني-ويب."""
    sql = f"""
        SELECT
            {_select_lang_clause(lang)},
            {_POPULARITY_SQL},
            0 AS score_pct
        FROM master
        WHERE id = %(id)s
              AND (last_time IS NULL OR last_time >= CURRENT_DATE)
              AND NOT COALESCE(is_suspended, FALSE)
        LIMIT 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"id": store_pk})
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="store not found")
    return StoreResult(
        **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en")},
        store_tags=_parse_tags(row.get("store_tags")),
        store_tags_en=_parse_tags(row.get("store_tags_en")),
    )


# تطابق دقيق على store_id (الـ slug في الموقع) + تفاصيل كاملة. يحلّ مشكلة الموقع
# الذي كان يعتمد على البحث ثم fallback لأول نتيجة (قد يعرض متجراً خاطئاً عند آلاف
# المتاجر). store_id لا يحتوي شرطة مائلة، لكن نستخدم :path احتياطاً للأحرف الخاصة.
@router.get("/by-slug/{slug:path}", response_model=StoreResult)
def get_coupon_by_slug(
    slug: str,
    lang: Literal["ar", "en"] = Query(default="ar"),
    conn=Depends(get_db),
):
    """التفاصيل الكاملة لمتجر بمطابقة store_id دقيقة — لصفحات المتجر في الموقع."""
    sql = f"""
        SELECT
            {_select_lang_clause(lang)},
            {_POPULARITY_SQL},
            0 AS score_pct
        FROM master
        WHERE store_id = %(slug)s
              AND (last_time IS NULL OR last_time >= CURRENT_DATE)
              AND NOT COALESCE(is_suspended, FALSE)
        LIMIT 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"slug": slug})
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="store not found")
    return StoreResult(
        **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en")},
        store_tags=_parse_tags(row.get("store_tags")),
        store_tags_en=_parse_tags(row.get("store_tags_en")),
    )
