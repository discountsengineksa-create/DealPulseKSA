"""
Helper مستقل لمعرفة الـ store_ids المُترندة الآن — لتقاط snapshot
دقيق في `story_views.was_trending` لحظة فتح الستوري.

يطابق منطق `/api/v1/trend/daily` و `/weekly` بمصدر `all` تماماً
(لأن الستوري نفسه يستهلك `/trend/daily?source=mini` لتلوين الحلقات
البرتقالية، لكن snapshot للسجل يجب أن يعكس "ترند فعلياً الآن" بغضّ
النظر عن المنصة — العميل شاف ناري سواء من ويب أو ميني-ويب).

نسخة منفصلة عن `api/routers/trend.py` لتفادي circular imports
(router يستورد FastAPI/Pydantic غير لازمة هنا) ولفصل اهتمام
الـ snapshot عن الـ HTTP serving.

cache 60 ثانية مطابق لـ trend router — يجنبنا حساب الخوارزمية
على كل INSERT في `/track/story-view`.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone

from psycopg2.extras import RealDictCursor

from api.utils.trend import (
    apply_overrides,
    compute_trend,
    person_key,
)

_RIYADH_OFFSET = timedelta(hours=3)
_CACHE_TTL_SECONDS = 60

# in-process cache: قيمة واحدة (set من store_ids المترندة الآن)
_cache_lock = threading.Lock()
_cache_ts: float = 0.0
_cache_value: set[str] = set()


def _load_events(conn) -> list[dict]:
    """نفس منطق _load_events في trend router لكن مع حد زمني (8 أيام)
    لتقليل عبء الحساب — أبعد من نافذة الأسبوعي بيوم احتياط."""
    sql = """
        SELECT a.action_time, a.action_type, a.store_id, a.user_id,
               COALESCE(a.source, 'bot') AS source,
               encode(a.ip_hash, 'hex')  AS ip_hex
        FROM   action_logs a
        WHERE  a.action_type IN ('click_link', 'copy_coupon', 'search')
          AND  a.store_id IS NOT NULL
          AND  TRIM(a.store_id) <> ''
          AND  a.action_time >= NOW() - INTERVAL '8 days'
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    out: list[dict] = []
    for r in rows:
        at = r["action_time"]
        if at.tzinfo is not None:
            at = at.astimezone(timezone.utc).replace(tzinfo=None)
        at_r = at + _RIYADH_OFFSET
        out.append({
            "time": at_r,
            "action_type": r["action_type"],
            "store_id": r["store_id"],
            "person_key": person_key(r["source"], r["user_id"], r["ip_hex"]),
        })
    return out


def _load_favorites(conn) -> list[dict]:
    sql = """
        SELECT uf.store_id, uf.created_at
        FROM   user_favorites uf
        WHERE  COALESCE(uf.kind, 'store') = 'store'
          AND  uf.store_id IS NOT NULL
          AND  TRIM(uf.store_id) <> ''
          AND  uf.created_at >= NOW() - INTERVAL '8 days'
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        rows = cur.fetchall()
    out: list[dict] = []
    for r in rows:
        ca = r["created_at"]
        if ca.tzinfo is not None:
            ca = ca.astimezone(timezone.utc).replace(tzinfo=None)
        ca_r = ca + _RIYADH_OFFSET
        out.append({"store_id": r["store_id"], "created_at": ca_r})
    return out


def _load_overrides(conn) -> tuple[dict[int, str], dict[int, str]]:
    """يرجع (daily_overrides, weekly_overrides)."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT window_kind, rank, store_id FROM trend_overrides"
            )
            daily: dict[int, str] = {}
            weekly: dict[int, str] = {}
            for window_kind, rank, store_id in cur.fetchall():
                target = daily if window_kind == "daily" else weekly
                target[rank] = store_id
            return daily, weekly
    except Exception:
        # rollback عشان transaction ما تعلق على الـ connection
        try:
            conn.rollback()
        except Exception:
            pass
        return {}, {}


def _load_active_store_ids(conn) -> set[str]:
    """نفس فلتر الماستر النشط الذي يستخدمه trend router."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT store_id FROM master
             WHERE store_id IS NOT NULL AND TRIM(store_id) <> ''
               AND (last_time IS NULL OR last_time >= CURRENT_DATE)
            """
        )
        return {row[0] for row in cur.fetchall()}


def compute_trending_store_ids(conn) -> set[str]:
    """
    يرجع set من store_ids المترندة حالياً = (يومي top-3) ∪ (أسبوعي top-7).

    هذا هو نفس signal الذي تستخدمه `miniapp.html` لتلوين حلقات الستوري
    البرتقالية (`isTrendNow(s)` → `DAILY_TREND_IDS` ∪ `WEEKLY_TREND_IDS`).

    cache 60 ثانية في الذاكرة. الفشل يرجع set فارغة (يفضّل أن يُسجَّل
    الـ view مع was_trending=False بدل أن يفشل INSERT كاملاً).
    """
    global _cache_ts, _cache_value
    now_ts = time.monotonic()

    with _cache_lock:
        if _cache_value and (now_ts - _cache_ts) < _CACHE_TTL_SECONDS:
            return _cache_value

    # حساب جديد خارج القفل
    try:
        events = _load_events(conn)
        favorites = _load_favorites(conn)
        active_ids = _load_active_store_ids(conn)

        events = [e for e in events if e["store_id"] in active_ids]
        favorites = [f for f in favorites if f["store_id"] in active_ids]

        now_r = (datetime.now(timezone.utc).replace(tzinfo=None)
                 + _RIYADH_OFFSET)
        daily_start = now_r.replace(hour=0, minute=0, second=0, microsecond=0)
        weekly_start = now_r - timedelta(days=7)

        daily_raw = compute_trend(events, favorites, daily_start, now_r, 13)
        weekly_raw = compute_trend(events, favorites, weekly_start, now_r, 20)
        daily_ov, weekly_ov = _load_overrides(conn)
        pinned_weekly_ids = set(weekly_ov.values())

        # اليومي (مع overrides + padding من الأسبوعي عند الحاجة)
        daily_top = apply_overrides(daily_raw, daily_ov, 3)
        if len(daily_top) < 3:
            existing = {it["store_id"] for it in daily_top}
            weekly_pad = apply_overrides(weekly_raw, weekly_ov, 20)
            pad = [it for it in weekly_pad
                   if it["store_id"] not in existing
                   and it["store_id"] not in pinned_weekly_ids]
            daily_top = (daily_top + pad)[:3]
        daily_ids = {it["store_id"] for it in daily_top}

        # الأسبوعي مستقل (يستبعد المعروض في اليومي ما عدا المثبّت يدوياً للأسبوعي)
        ids_to_exclude = daily_ids - pinned_weekly_ids
        weekly_filtered = [it for it in weekly_raw
                           if it["store_id"] not in ids_to_exclude]
        weekly_top = apply_overrides(weekly_filtered, weekly_ov, 7)
        weekly_ids = {it["store_id"] for it in weekly_top}

        result = daily_ids | weekly_ids
    except Exception:
        # لا نكسر INSERT الستوري بسبب فشل الـ snapshot
        try:
            conn.rollback()
        except Exception:
            pass
        result = set()

    with _cache_lock:
        _cache_ts = now_ts
        _cache_value = result
    return result
