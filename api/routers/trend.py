"""
نقاط نهاية «الترند» للموقع والميني-ويب.

GET /api/v1/trend/daily   → أعلى 3 متاجر (الأعلى طلباً / الأكثر شعبية / الأوسع انتشاراً)
                            من 12:00 ص بتوقيت الرياض إلى الآن.
GET /api/v1/trend/weekly  → أعلى 7 متاجر (المراكز 1-3 بألقاب، 4-7 بترقيم)
                            آخر 7 أيام rolling.

كلاهما يدعم ?source=all|bot|web|mini للتجزئة حسب المنصة.

ملاحظات معمارية:
- الخوارزمية مطابقة تماماً لمنطق الداشبورد (لكن بـ Python نقي بلا pandas).
- نتيجة كل (window × source) مخزّنة 60 ثانية في ذاكرة العملية — يكفي للموقع
  الذي يستخدم Next.js revalidate=60 ولا يخلق ضغطاً إضافياً.
- المستخدم النهائي ما يشوف نقاط ولا breakdown؛ نُرجعها للاكتمال (debugging /
  استخدام إداري)، والواجهة الأمامية ترسم بالـ store_id + logo_url فقط.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel

from api.db import get_db
from api.utils.trend import (
    apply_anti_spam,
    apply_overrides,
    assign_rank_titles,
    compute_trend,
    person_key,
)

router = APIRouter(prefix="/trend", tags=["trend"])

# ── خرائط فلتر المصدر ────────────────────────────────────────────────────────
SourceLiteral = Literal["all", "bot", "web", "mini"]

SOURCE_ACTION_FILTERS: dict[str, tuple[str, ...] | None] = {
    "all": None,
    "bot": ("bot",),
    "web": ("web",),
    "mini": ("telegram_miniapp", "miniapp"),
}
SOURCE_FAV_FILTERS: dict[str, tuple[str, ...] | None] = {
    "all": None,
    "bot": ("bot",),
    "web": ("web",),
    "mini": ("miniapp",),
}

# ── توقيت الرياض (UTC+3 ثابت — لا توقيت صيفي في السعودية) ───────────────────
RIYADH_TZ = timezone(timedelta(hours=3))

# ── كاش بسيط داخل العملية: (window, source, top_n) → (ts, result) ──────────
_CACHE_TTL_SECONDS = 60
_cache: dict[tuple[str, str, int], tuple[float, list[dict]]] = {}
_cache_lock = threading.Lock()


# ── Pydantic schemas للتوثيق التلقائي (/docs) ────────────────────────────────
class TrendBreakdown(BaseModel):
    clicks: int
    searches: int
    copies: int
    favs: int
    unique_users: int


class TrendItem(BaseModel):
    rank: int
    rank_title: str
    store_id: str
    store_name: str
    name_en: str | None = None     # للعرض في وضع اللغة الإنجليزية
    logo_url: str | None = None
    cloaked_slug: str | None = None
    score: int
    breakdown: TrendBreakdown


class TrendResponse(BaseModel):
    window: Literal["daily", "weekly"]
    source: SourceLiteral
    window_start: str         # ISO 8601 بتوقيت الرياض
    window_end: str           # ISO 8601 بتوقيت الرياض (= now)
    generated_at: str         # ISO 8601 (UTC)
    items: list[TrendItem]


# ── محمّلات البيانات من DB ─────────────────────────────────────────────────
def _load_events(conn, source_filter: tuple[str, ...] | None) -> list[dict]:
    """يسحب الأحداث الخام بتوقيت UTC ثم يحوّلها لتوقيت الرياض (naive)."""
    sql = """
        SELECT a.action_time, a.action_type, a.store_id, a.user_id,
               COALESCE(a.source, 'bot') AS source,
               encode(a.ip_hash, 'hex')  AS ip_hex
        FROM   action_logs a
        WHERE  a.action_type IN ('click_link', 'copy_coupon', 'search')
          AND  a.store_id IS NOT NULL
          AND  TRIM(a.store_id) <> ''
    """
    params: list = []
    if source_filter is not None:
        sql += " AND COALESCE(a.source, 'bot') = ANY(%s)"
        params.append(list(source_filter))
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    out: list[dict] = []
    riyadh_offset = timedelta(hours=3)
    for r in rows:
        at = r["action_time"]
        # ضمان naive UTC ثم إزاحة للرياض (يطابق نمط الداشبورد)
        if at.tzinfo is not None:
            at = at.astimezone(timezone.utc).replace(tzinfo=None)
        at_r = at + riyadh_offset
        out.append({
            "time": at_r,
            "action_type": r["action_type"],
            "store_id": r["store_id"],
            "person_key": person_key(r["source"], r["user_id"], r["ip_hex"]),
        })
    return out


def _load_favorites(conn, fav_filter: tuple[str, ...] | None) -> list[dict]:
    """يسحب المفضلة (kind='store' فقط) مع تحويل created_at للرياض."""
    sql = """
        SELECT uf.store_id, uf.created_at
        FROM   user_favorites uf
        WHERE  COALESCE(uf.kind, 'store') = 'store'
          AND  uf.store_id IS NOT NULL
          AND  TRIM(uf.store_id) <> ''
    """
    params: list = []
    if fav_filter is not None:
        sql += " AND uf.platform = ANY(%s)"
        params.append(list(fav_filter))
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    out: list[dict] = []
    riyadh_offset = timedelta(hours=3)
    for r in rows:
        ca = r["created_at"]
        if ca.tzinfo is not None:
            ca = ca.astimezone(timezone.utc).replace(tzinfo=None)
        ca_r = ca + riyadh_offset
        out.append({"store_id": r["store_id"], "created_at": ca_r})
    return out


def _load_trend_overrides(conn, window: str) -> dict[int, str]:
    """
    يقرأ التجاوزات اليدوية للنافذة المُعطاة (admin pins من trend_overrides).
    يُرجع {rank: store_id}. لو الجدول غير موجود (قبل تطبيق migration 030)،
    نُرجع dict فاضي حتى ما نكسر الـ API على الأنظمة القديمة.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT rank, store_id FROM trend_overrides WHERE window_kind = %s",
                (window,),
            )
            return {row[0]: row[1] for row in cur.fetchall()}
    except Exception:
        # rollback عشان الـ transaction ما تعلق على الـ connection بعدنا.
        try:
            conn.rollback()
        except Exception:
            pass
        return {}


def _load_master_meta(conn) -> dict[str, dict]:
    """
    خرائط المتجر للعرض: store_id → {logo_url, cloaked_slug}.
    يفضّل صفاً بشعار عند التكرار (DISTINCT ON) — نفس منطق الداشبورد.
    يستبعد المنتهية (last_time < اليوم).
    """
    sql = """
        SELECT DISTINCT ON (store_id)
               store_id,
               COALESCE(name_en, '')       AS name_en,
               COALESCE(logo_url, '')      AS logo_url,
               COALESCE(cloaked_slug, '')  AS cloaked_slug
        FROM   master
        WHERE  store_id IS NOT NULL AND TRIM(store_id) <> ''
          AND  (last_time IS NULL OR last_time >= CURRENT_DATE)
        ORDER  BY store_id,
                  (CASE WHEN logo_url IS NOT NULL AND logo_url <> '' THEN 0 ELSE 1 END)
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    return {r["store_id"]: {"name_en": r["name_en"],
                              "logo_url": r["logo_url"],
                              "cloaked_slug": r["cloaked_slug"]}
            for r in rows}


# ── الحساب الرئيسي (مع كاش) ─────────────────────────────────────────────────
def _compute_window(conn, window: str, source: str, top_n: int) -> list[dict]:
    """يحسب الترند لنافذة محددة. ليس مكشوفاً مباشرة — يُستدعى عبر _get_cached."""
    src_filter = SOURCE_ACTION_FILTERS[source]
    fav_filter = SOURCE_FAV_FILTERS[source]

    events = _load_events(conn, src_filter)
    favorites = _load_favorites(conn, fav_filter)
    meta = _load_master_meta(conn)

    if window not in ("daily", "weekly"):
        raise ValueError(f"Unknown window: {window}")

    # فلترة المتاجر بالماستر النشط (يستبعد ما خرج)
    active_ids = set(meta.keys())
    events = [e for e in events if e["store_id"] in active_ids]
    favorites = [f for f in favorites if f["store_id"] in active_ids]

    # ── حساب كلا النافذتين داخلياً (مطلوب للتأكد من استقلالهما) ─────────────
    # نحتاج معرفة ما سيظهر في اليومي قبل أن نختار الأسبوعي، حتى نُقصي متاجر
    # اليومي من الأسبوعي (الاستقلال المطلوب من المالك).
    now_r = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
    daily_start = now_r.replace(hour=0, minute=0, second=0, microsecond=0)
    weekly_start_dt = now_r - timedelta(days=7)
    wstart = daily_start if window == "daily" else weekly_start_dt

    daily_raw    = compute_trend(events, favorites, daily_start,    now_r, 13)   # 3 + 10 buffer
    weekly_raw   = compute_trend(events, favorites, weekly_start_dt, now_r, 20)  # 7 + 13 buffer
    daily_overrides  = _load_trend_overrides(conn, "daily")
    weekly_overrides = _load_trend_overrides(conn, "weekly")
    pinned_weekly_ids = set(weekly_overrides.values())

    # ── اليومي النهائي (مع overrides + padding من الأسبوعي عند الحاجة) ──────
    # padding يستبعد المتاجر المثبّتة للأسبوعي (تخصّ الأسبوعي، ما نشيلها لليومي)
    daily_after_ov = apply_overrides(daily_raw, daily_overrides, 3)
    if len(daily_after_ov) < 3:
        existing = {it["store_id"] for it in daily_after_ov}
        weekly_after_ov_for_pad = apply_overrides(weekly_raw, weekly_overrides, 20)
        pad = [it for it in weekly_after_ov_for_pad
               if it["store_id"] not in existing
               and it["store_id"] not in pinned_weekly_ids]
        daily_after_ov = (daily_after_ov + pad)[:3]
    daily_displayed_ids = {it["store_id"] for it in daily_after_ov}

    # ── اختيار النتيجة بحسب النافذة المطلوبة ─────────────────────────────
    if window == "daily":
        raw = daily_after_ov[:top_n]
    else:  # weekly
        # الأسبوعي يستبعد كل متاجر اليومي المعروضة (ما عدا المثبّتة يدوياً للأسبوعي).
        # المالك: "الترند الأسبوعي مستقل عن اليومي بالكامل".
        ids_to_exclude = daily_displayed_ids - pinned_weekly_ids
        weekly_filtered = [it for it in weekly_raw
                           if it["store_id"] not in ids_to_exclude]
        raw = apply_overrides(weekly_filtered, weekly_overrides, top_n)

    items = assign_rank_titles(raw)

    # إثراء بالميتاداتا للعرض
    for it in items:
        sid = it["store_id"]
        m = meta.get(sid, {})
        it["store_name"] = sid     # store_id = الاسم العربي في هذا الـ codebase
        it["name_en"] = m.get("name_en") or None   # للعرض في وضع EN
        it["logo_url"] = m.get("logo_url") or None
        it["cloaked_slug"] = m.get("cloaked_slug") or None
        # تنسيق الـ breakdown داخل كائن فرعي (يطابق Pydantic schema)
        it["breakdown"] = {
            "clicks": it.pop("clicks"),
            "searches": it.pop("searches"),
            "copies": it.pop("copies"),
            "favs": it.pop("favs"),
            "unique_users": it.pop("unique_users"),
        }

    return items, wstart, now_r


def _get_cached(conn, window: str, source: str, top_n: int):
    key = (window, source, top_n)
    now_ts = time.monotonic()
    with _cache_lock:
        cached = _cache.get(key)
        if cached and (now_ts - cached[0]) < _CACHE_TTL_SECONDS:
            return cached[1]
    # احتساب جديد خارج القفل
    result = _compute_window(conn, window, source, top_n)
    with _cache_lock:
        _cache[key] = (now_ts, result)
    return result


def _build_response(window: str, source: str, top_n: int, conn) -> TrendResponse:
    items, wstart, wend = _get_cached(conn, window, source, top_n)
    return TrendResponse(
        window=window,
        source=source,
        window_start=wstart.replace(tzinfo=RIYADH_TZ).isoformat(),
        window_end=wend.replace(tzinfo=RIYADH_TZ).isoformat(),
        generated_at=datetime.now(timezone.utc).isoformat(),
        items=items,
    )


# ── Endpoints ────────────────────────────────────────────────────────────────
@router.get("/daily", response_model=TrendResponse)
def get_daily_trend(
    source: SourceLiteral = Query("all", description="all | bot | web | mini"),
    conn=Depends(get_db),
):
    """
    أعلى 3 متاجر من 12:00 ص (توقيت الرياض) إلى الآن.

    المراكز:
        1. الأعلى طلباً
        2. الأكثر شعبية
        3. الأوسع انتشاراً

    نقاط: نقر=1 · بحث=2 · نسخ=3 · مفضلة=4.
    قاعدة Anti-Spam: لكل (مستخدم × متجر × نوع فعل) أول 2 خلال ساعة تُحسب،
    ثم تبريد لـ 5 ساعات قبل فتح نافذة جديدة.
    """
    return _build_response("daily", source, top_n=3, conn=conn)


@router.get("/weekly", response_model=TrendResponse)
def get_weekly_trend(
    source: SourceLiteral = Query("all", description="all | bot | web | mini"),
    conn=Depends(get_db),
):
    """
    أعلى 7 متاجر — آخر 7 أيام rolling (يتحرك مع الوقت ثانية بثانية).

    المراكز 1-3: الأعلى طلباً / الأكثر شعبية / الأوسع انتشاراً.
    المراكز 4-7: المركز الرابع، الخامس، السادس، السابع.

    نفس نظام النقاط و Anti-Spam كالـ daily.
    """
    return _build_response("weekly", source, top_n=7, conn=conn)
