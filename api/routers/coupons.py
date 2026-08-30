from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from api.db import get_db
from api.schemas.coupon import SearchResponse, StoreResult
from api.utils.settings import get_setting

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


# قنوات النشر (master.publish_channels) — تُمرَّر كبارامتر channel.
# الموقع يطلب 'website' (الافتراضي)؛ الميني-ويب والبوت يطلبان 'bot'.
# NULL في القاعدة = كل القنوات (توافق المتاجر القديمة).
_VALID_CHANNELS = {"website", "bot", "instagram", "threads", "facebook"}


def _channel_like(channel: str) -> str:
    """نمط ILIKE آمن لقناة النشر (whitelist؛ غير المعروف → website)."""
    ch = channel if channel in _VALID_CHANNELS else "website"
    return f"%{ch}%"


@router.get("/top-favorited")
def get_top_favorited_stores(
    limit: int = Query(default=10, ge=1, le=20),
    channel: str = Query(default="website"),
    conn=Depends(get_db),
):
    """أبرز المتاجر = أكثر المتاجر تفضيلاً عبر القنوات الثلاث (bot+miniapp+web).
    يُستخدم في الصف الأفقي تحت الستوري على الموقع/الميني. الترتيب من الأكثر
    تفضيلاً تنازلياً؛ المتاجر المنتهية/المعلَّقة مُستثناة. ?channel=bot للميني-ويب.
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
                WHERE (m.last_time IS NULL OR m.last_time > CURRENT_DATE)
                  AND NOT COALESCE(m.is_suspended, FALSE)
                  AND (m.publish_channels IS NULL OR m.publish_channels ILIKE %(chpat)s)
                ORDER BY fc.fav_count DESC, m.store_id ASC
                LIMIT %(limit)s
                """,
                {"limit": limit, "chpat": _channel_like(channel)},
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


@router.get("/site-flags")
def get_site_flags():
    """أعلام تشغيل الموقع العامة (بلا مصادقة) — يقرأها الويب في كل تحميل.

    login_gate_enabled=true (الافتراضي) ⇒ بوّابة تسجيل الدخول مُفعّلة: الأكواد
    محجوبة خلف تسجيل الدخول. false ⇒ البوّابة مُطفأة: الموقع مفتوح للجميع،
    الأكواد والزيارة تظهر بلا تسجيل، لكن الستوري والمفضلة تبقى للمسجّلين فقط
    (وصفحات الدخول/التسجيل تبقى متاحة عشانها). يتحكّم فيه الأدمن من صفحة
    «إدارة الموقع» في الداشبورد عبر platform_settings."""
    raw = get_setting("web_login_gate_enabled", "1")
    return {"login_gate_enabled": (raw or "1") != "0"}


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


# ── صفحة المتجر = أصل SEO دائم (evergreen) ───────────────────────────────────
# صفحة `/store/{id}` وبطاقتها في الدليل والـsitemap يجب أن تبقى 200 وموجودة حتى بعد
# انتهاء الكوبون. الفلترة بالانتهاء كانت تُحوّلها 404 فتكسر مئات الروابط الداخلية
# وbreadcrumbs وتوقف زحف Google (السبب الجذري، 2026-07). الحلّ: على قناة الموقع لا
# نفلتر بالانتهاء (المتجر يبقى)، والكوبون/الخصم يُفرَّغ في المخرجات عبر CASE إذا
# انتهى فلا يظهر كود ميّت كأنه فعّال (صدق البيانات). قنوات البوت/الميني تبقى على
# الكوبونات الفعّالة فقط (سطح صفقات لا دليل SEO دائم).
_OFFER_ACTIVE_SQL = "(last_time IS NULL OR last_time > CURRENT_DATE)"


def _expiry_where(channel: str, *, detail: bool = False, evergreen: bool = False) -> str:
    """شرط الانتهاء في WHERE.

    • **الكتالوج والبحث والأبرز — كل القنوات:** المتجر المنتهي يختفي فوراً من
      واجهات العرض (القائمة، البحث، عدّاد المتاجر) إلى حين تجديد التاريخ.
    • **صفحة المتجر المفردة على الموقع فقط (`detail=True`):** تبقى 200 بلا كود.
      المقالات تحمل ٧٥ رابطاً داخلياً إليها، وتحويلها 404 كسر شبكة الروابط وأوقف
      زحف Google في 2026-07-21. البوت والميني يفلترانها كالمعتاد.
    • **الخريطة على الموقع فقط (`evergreen=True`):** تُدرج المنتهي كذلك.
      إخراج صفحة ترجّع 200 من الـsitemap يجعلها أصلاً حيّاً بلا إشارة اكتشاف —
      وميزانية الزحف هنا شحيحة (٢٤٤ صفحة «مكتشفة لم تُفهرس»)، فالإخراج يذبلها
      بصمت بينما نيّة الإصلاح كانت الحفاظ عليها. لا يمسّ الكتالوج ولا البحث.
    """
    if channel == "website" and (detail or evergreen):
        return ""
    return f"AND {_OFFER_ACTIVE_SQL}"


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
            affiliate_link,
            -- الكوبون/الخصم/العرض محتوى مؤقّت: يُفرَّغ إذا انتهى فلا يظهر كود ميّت
            -- كأنه فعّال، مع بقاء المتجر نفسه ظاهراً (evergreen على قناة الموقع).
            CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN public_coupon ELSE NULL END AS public_coupon,
            CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE)
                 THEN COALESCE(NULLIF(extra_offer_en, ''), extra_offer) ELSE NULL END AS extra_offer,
            CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN extra_offer_en ELSE NULL END AS extra_offer_en,
            COALESCE(NULLIF(store_bio_en, ''),   store_bio)     AS store_bio,
            store_bio_en,
            description,
            COALESCE(NULLIF(store_tags_en, ''),  store_tags)    AS store_tags,
            store_tags_en,
            occasions,
            CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN discount_value ELSE NULL END AS discount_value,
            total_coupon_copies, total_link_clicks, is_trending_bool AS is_trending, priority_score_int AS priority_score,
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
        id, store_id, name_en, affiliate_link,
        -- الكوبون/الخصم/العرض يُفرَّغ إذا انتهى (المتجر يبقى evergreen على الموقع).
        CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN public_coupon ELSE NULL END AS public_coupon,
        CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN extra_offer    ELSE NULL END AS extra_offer,
        CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN extra_offer_en ELSE NULL END AS extra_offer_en,
        store_bio,   store_bio_en,
        description,
        store_tags,  store_tags_en,
        occasions,
        CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN discount_value ELSE NULL END AS discount_value,
        total_coupon_copies, total_link_clicks, is_trending_bool AS is_trending, priority_score_int AS priority_score,
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
            CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE)
                 THEN COALESCE(NULLIF(extra_offer_en, ''), extra_offer) ELSE NULL END AS extra_offer,
            COALESCE(NULLIF(store_tags_en, ''),  store_tags)     AS store_tags,
            CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN discount_value ELSE NULL END AS discount_value,
            is_trending_bool AS is_trending, priority_score_int AS priority_score,
            COALESCE(is_promoted, FALSE) AS is_promoted,
            logo_url, story_ring_color, total_coupon_copies, total_link_clicks
        """
    return """
        id, store_id, name_en,
        CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN extra_offer    ELSE NULL END AS extra_offer,
        store_tags,
        CASE WHEN (last_time IS NULL OR last_time > CURRENT_DATE) THEN discount_value ELSE NULL END AS discount_value,
        is_trending_bool AS is_trending, priority_score_int AS priority_score,
        COALESCE(is_promoted, FALSE) AS is_promoted,
        logo_url, story_ring_color, total_coupon_copies, total_link_clicks
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
              AND (last_time IS NULL OR last_time > CURRENT_DATE)
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
    limit: int = Query(default=5000, ge=1, le=5000),   # الكتالوج كامل افتراضياً
    # كان 50: أي متجر خارج الخمسين يسقط من الصفحة الرئيسية — ومعه صف الستوري
    # الذي كان يُبنى بفلترة هذه القائمة. «منصة زد» تصدّرت الترند اليومي
    # والأسبوعي وغابت عن الصف لأنها المتجر 52 من 52. الكتالوج صغير، فالسقف
    # الافتراضي المنخفض كان يكلّف أكثر مما يوفّر.
    lang: Literal["ar", "en"] = Query(default="ar"),
    view: Literal["full", "light"] = Query(default="full"),
    channel: str = Query(default="website"),
    include_expired: bool = Query(
        default=False,
        description="خريطة الموقع فقط: يضمّ المتاجر المنتهية (channel=website حصراً)",
    ),
    conn=Depends(get_db),
):
    """إرجاع المتاجر مرتبةً: المروّجة ثم الترند ثم بالمعرّف. ?lang=en يبدّل الحقول.
    ?view=light → قائمة خفيفة سريعة (بلا ستوري/أكواد إضافية/وصف/popularity) للكتالوج
    الكامل (آلاف المتاجر)؛ التفاصيل تُجلب لكل متجر عبر /coupons/detail/{id}.
    ?channel=bot → قائمة الميني-ويب/البوت (افتراضي website).

    ⚠️ `include_expired=true` **للـsitemap وحده** — صفحة المتجر المنتهي ترجّع 200
    فيجب أن تبقى في الخريطة، لكنها تظلّ خارج الكتالوج والبحث وعدّاد المتاجر.
    لا تستعمله في واجهة عرض: سيُظهر متجراً بلا كود كأنه معروض."""
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
        WHERE NOT COALESCE(is_suspended, FALSE)
              {_expiry_where(channel, evergreen=include_expired)}
              AND (publish_channels IS NULL OR publish_channels ILIKE %(chpat)s)
        ORDER BY
            COALESCE(is_promoted, FALSE) DESC,
            is_trending_bool                DESC,
            priority_score_int              DESC,
            id ASC
        LIMIT %(limit)s
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"limit": limit, "chpat": _channel_like(channel)})
        rows = cur.fetchall()

    results = [
        StoreResult(
            **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en", "occasions")},
            store_tags=_parse_tags(row.get("store_tags")),
            store_tags_en=_parse_tags(row.get("store_tags_en")),
            occasions=_parse_tags(row.get("occasions")),
        )
        for row in rows
    ]
    return SearchResponse(query="", total=len(results), capped=(len(results) == limit), results=results)


# تطبيع عربي داخل SQL بلا الاعتماد على دالة DB — يبقى البحث سليماً حتى لو
# نُشر الكود قبل تشغيل migration_070 (الذي يُنشئ normalize_ar و search_concepts).
# نفس قواعد api/utils/arabic_search.normalize_ar: أإآٱ→ا، ى→ي، ة→ه، حذف التطويل/التشكيل.
def _norm_sql(col: str) -> str:
    return (
        f"regexp_replace(translate(lower(coalesce({col}, '')), "
        f"'أإآٱىة', 'اااايه'), '[ـً-ْ]', '', 'g')"
    )


@router.get("/search", response_model=SearchResponse)
def search_coupons(
    q: str = Query(..., min_length=2, max_length=100, description="نص البحث"),
    limit: int = Query(default=20, ge=1, le=50),
    lang: Literal["ar", "en"] = Query(default="ar"),
    channel: str = Query(default="website"),
    conn=Depends(get_db),
):
    """
    البحث الذكي — ثلاث طبقات مرتّبة بالتدرّج:

    1. **اسم المتجر** — تطابق دقيق، ثم الأقرب عند الخطأ الإملائي (trigram).
       التطبيع يوحّد صور الحرف («نمشى»→«نمشي») والمسافات («ترنديول»→«ترند يول»).
    2. **مفهوم/قسم** — الاستعلام (أو أقرب صورة له) موجود في `search_concepts`
       كمرادف/إملاء/كلمة-منتج → وسم قسم. النتيجة: **كل** متاجر ذلك القسم
       مرتّبةً بالشعبية. («أحذية»→كل متاجر `أحذيه` ، «خواتم»→كل متاجر `مجوهرات`).
    3. **نبذة المتجر** ثم **تطابق ضبابي بعيد** — آخر تدرّج.

    كل صفّ يحمل `match_type` لتجمّعه الواجهة بعناوين.
    - ?lang=en يبدّل قيم الاستجابة للإنجليزيّة (Fallback للعربية إذا فارغة).
    - ?channel=bot يقصر النتائج على متاجر قناة البوت/الميني (افتراضي website).
    """
    from api.utils.arabic_search import normalize_ar, strip_ws

    q = q.strip()
    q_norm = normalize_ar(q)
    q_no_ws = strip_ws(q_norm)

    # ── الطبقة ٢: حلّ المفاهيم (مرادف/إملاء/كلمة-منتج → وسوم canonical) ──────
    # يُتخطّى بأمان قبل migration_070 (الجدول غير موجود).
    concept_tags: list[str] = []
    concept_weights: list[float] = []
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('search_concepts')")
        if cur.fetchone()[0] is not None and len(q_norm) >= 2:
            cur.execute(
                """
                SELECT canonical_tag, MAX(weight) AS w
                FROM search_concepts
                WHERE term = %(q)s
                   OR (length(%(q)s) >= 3 AND similarity(term, %(q)s) >= 0.55)
                GROUP BY canonical_tag
                ORDER BY w DESC, canonical_tag
                LIMIT 6
                """,
                {"q": q_norm},
            )
            for tag, w in cur.fetchall():
                concept_tags.append(normalize_ar(tag))
                concept_weights.append(float(w))

    # ── الطبقة ٣ (احتياط أخير): جسر المدوّنة — كلمة الاستعلام في نصّ مقال ضيّق
    # الموضوع → متاجر ذلك المقال، مع عنوانه. FTS بترتيب ts_rank، أعلى ٣ مقالات.
    # يُتخطّى بأمان قبل migration_070 / قبل ملء blog_bridge.
    blog_ids: list[str] = []
    blog_titles: list[str] = []
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('blog_bridge')")
        if cur.fetchone()[0] is not None and len(q_norm) >= 3:
            cur.execute(
                """
                SELECT slug, title, store_ids,
                       ts_rank(to_tsvector('simple', body_norm),
                               plainto_tsquery('simple', %(q)s)) AS rank
                FROM blog_bridge
                WHERE to_tsvector('simple', body_norm)
                      @@ plainto_tsquery('simple', %(q)s)
                ORDER BY rank DESC
                LIMIT 3
                """,
                {"q": q_norm},
            )
            seen: set[str] = set()
            for _slug, title, store_ids, _rank in cur.fetchall():
                for sid in _parse_tags(store_ids):
                    if sid and sid not in seen:
                        seen.add(sid)
                        blog_ids.append(sid)
                        blog_titles.append(title or "")

    n_id, n_name, n_bio, n_tags = (
        _norm_sql("store_id"), _norm_sql("name_en"),
        _norm_sql("store_bio"), _norm_sql("store_tags"),
    )

    sql = f"""
        WITH concept(tag, w) AS (
            SELECT * FROM unnest(%(c_tags)s::text[], %(c_weights)s::real[])
        ),
        scored AS (
            SELECT
                {_select_lang_clause(lang)},
                {_POPULARITY_SQL},
                GREATEST(
                    similarity({n_id},   %(qn)s),
                    similarity({n_name}, %(qn)s),
                    similarity({n_bio},  %(qn)s) * 0.35,
                    similarity(lower(coalesce(store_bio_en, '')), lower(%(q)s)) * 0.35
                ) AS name_score,
                (
                    SELECT max(c.w) FROM concept c
                    WHERE length(c.tag) >= 2
                      AND position(c.tag in {n_tags}) > 0
                ) AS concept_w,
                (
                    length(%(qn)s) >= 2 AND (
                        position(%(qn)s in {n_id})   > 0
                        OR position(%(qn)s in {n_name}) > 0
                        OR (length(%(qnw)s) >= 3
                            AND position(%(qnw)s in replace({n_id}, ' ', '')) > 0)
                    )
                ) AS name_hit,
                (
                    length(%(qn)s) >= 3 AND (
                        position(%(qn)s in {n_bio}) > 0
                        OR position(lower(%(q)s) in lower(coalesce(store_bio_en, ''))) > 0
                    )
                ) AS bio_hit,
                (
                    SELECT bt.title
                    FROM unnest(%(b_ids)s::text[], %(b_titles)s::text[]) bt(sid, title)
                    WHERE bt.sid = master.store_id
                    LIMIT 1
                ) AS via_article
            FROM master
            WHERE NOT COALESCE(is_suspended, FALSE)
              {_expiry_where(channel)}
              AND (publish_channels IS NULL OR publish_channels ILIKE %(chpat)s)
        )
        SELECT s.*,
            CASE
                WHEN name_hit OR name_score >= 0.40 THEN 'name'
                WHEN concept_w IS NOT NULL          THEN 'concept'
                WHEN via_article IS NOT NULL        THEN 'blog'
                WHEN bio_hit                        THEN 'bio'
                ELSE 'fuzzy'
            END AS match_type,
            (LEAST(GREATEST(name_score, COALESCE(concept_w, 0)), 1.0) * 100)::int AS score_pct
        FROM scored s
        WHERE name_hit OR bio_hit OR concept_w IS NOT NULL
           OR via_article IS NOT NULL OR name_score > 0.25
        ORDER BY
            CASE
                WHEN name_hit              THEN 1
                WHEN name_score >= 0.40    THEN 2
                WHEN concept_w >= 1.0      THEN 3
                WHEN concept_w > 0         THEN 4
                WHEN via_article IS NOT NULL THEN 5
                WHEN bio_hit               THEN 6
                ELSE 7
            END,
            popularity_score DESC,
            name_score DESC,
            store_id ASC
        LIMIT %(limit)s
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {
            "q": q, "qn": q_norm, "qnw": q_no_ws,
            "c_tags": concept_tags, "c_weights": concept_weights,
            "b_ids": blog_ids, "b_titles": blog_titles,
            "limit": limit, "chpat": _channel_like(channel),
        })
        rows = cur.fetchall()

    results = [
        StoreResult(
            **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en", "occasions")},
            store_tags=_parse_tags(row.get("store_tags")),
            store_tags_en=_parse_tags(row.get("store_tags_en")),
            occasions=_parse_tags(row.get("occasions")),
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
    channel: str = Query(default="website"),
    conn=Depends(get_db),
):
    """التفاصيل الكاملة لمتجر بمعرّفه الرقمي (id)؛ يخدم «التفاصيل عند الطلب» للميني-ويب.
    ?channel=bot للميني-ويب (افتراضي website)."""
    sql = f"""
        SELECT
            {_select_lang_clause(lang)},
            {_POPULARITY_SQL},
            0 AS score_pct
        FROM master
        WHERE id = %(id)s
              AND NOT COALESCE(is_suspended, FALSE)
              {_expiry_where(channel, detail=True)}
              AND (publish_channels IS NULL OR publish_channels ILIKE %(chpat)s)
        LIMIT 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"id": store_pk, "chpat": _channel_like(channel)})
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="store not found")
    return StoreResult(
        **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en", "occasions")},
        store_tags=_parse_tags(row.get("store_tags")),
        store_tags_en=_parse_tags(row.get("store_tags_en")),
        occasions=_parse_tags(row.get("occasions")),
    )


# تطابق دقيق على store_id (الـ slug في الموقع) + تفاصيل كاملة. يحلّ مشكلة الموقع
# الذي كان يعتمد على البحث ثم fallback لأول نتيجة (قد يعرض متجراً خاطئاً عند آلاف
# المتاجر). store_id لا يحتوي شرطة مائلة، لكن نستخدم :path احتياطاً للأحرف الخاصة.
@router.get("/by-slug/{slug:path}", response_model=StoreResult)
def get_coupon_by_slug(
    slug: str,
    lang: Literal["ar", "en"] = Query(default="ar"),
    channel: str = Query(default="website"),
    conn=Depends(get_db),
):
    """التفاصيل الكاملة لمتجر بمطابقة store_id دقيقة — لصفحات المتجر في الموقع.
    افتراضي channel=website (صفحات الموقع)."""
    sql = f"""
        SELECT
            {_select_lang_clause(lang)},
            {_POPULARITY_SQL},
            0 AS score_pct
        FROM master
        WHERE store_id = %(slug)s
              AND NOT COALESCE(is_suspended, FALSE)
              {_expiry_where(channel, detail=True)}
              AND (publish_channels IS NULL OR publish_channels ILIKE %(chpat)s)
        LIMIT 1
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, {"slug": slug, "chpat": _channel_like(channel)})
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="store not found")
    return StoreResult(
        **{k: v for k, v in row.items() if k not in ("store_tags", "store_tags_en", "occasions")},
        store_tags=_parse_tags(row.get("store_tags")),
        store_tags_en=_parse_tags(row.get("store_tags_en")),
        occasions=_parse_tags(row.get("occasions")),
    )
