"""
Google Trends puller — يجلب درجة شعبية كل keyword من Google Trends في السعودية.

الاستخدام في "محرك الفرص":
  • المستخدم يضيف keyword (مثلاً "كود خصم نون") في seo_opportunity_keywords
  • الـ scheduler كل ساعة يستدعي refresh_keyword_trend(kw) لكل active keyword
  • يحفظ trend_score (0-100) + rising_pct (تغير ساعي ↗) في الجدول
  • الـ dashboard يعرضها مرتّبة → المستخدم يقرّر توليد صفحة لمن

نستخدم pytrends (مكتبة غير رسمية لـ Google Trends). Google ليس له API
رسمي لـ Trends، لذا pytrends تتعامل مع endpoint داخلي. قد يحدث rate-limit
أو تغييرات؛ كل دالة مغلّفة بـ try/except.
"""
from __future__ import annotations

import logging
import time
from typing import Any

_log = logging.getLogger("dp.seo.trends_puller")

# pytrends يبني client داخلياً عند الاستدعاء — نُنشئ instance واحد يُعاد استخدامه
# مع cookies session لتقليل rate-limit
_pytrends_client = None


def _get_client():
    """يُنشئ pytrends client بـ lazy init. يرجع None لو الـ import فشل."""
    global _pytrends_client
    if _pytrends_client is not None:
        return _pytrends_client
    try:
        from pytrends.request import TrendReq
        _pytrends_client = TrendReq(
            hl="ar-SA",       # لغة الواجهة العربية السعودية
            tz=180,            # AST = UTC+3
            timeout=(10, 25),  # connect, read
            retries=2,
            backoff_factor=0.5,
        )
        return _pytrends_client
    except Exception as exc:
        _log.error("pytrends import/init failed: %s", str(exc)[:300])
        return None


def fetch_keyword_score(keyword: str, *, geo: str = "SA",
                         timeframe: str = "now 1-d") -> dict[str, Any]:
    """
    يجلب درجة الاهتمام الحالية لـ keyword في منطقة معيّنة.

    Args:
        keyword: الكلمة المستهدفة (مثلاً "كود خصم نون")
        geo: ISO country code ("SA" للسعودية، "" للعالم)
        timeframe: نطاق Google Trends. الخيارات الشائعة:
          - "now 1-H"   آخر ساعة (دقة دقيقة)
          - "now 4-H"   آخر 4 ساعات
          - "now 1-d"   آخر 24 ساعة
          - "now 7-d"   آخر أسبوع
          - "today 1-m" آخر شهر

    Returns:
        {
          "ok": bool,
          "keyword": str,
          "trend_score": int (0-100, آخر نقطة في الـ timeseries),
          "trend_avg": float (متوسط الفترة كاملة),
          "rising_pct": float (% تغير آخر نقطة عن متوسط الفترة),
          "data_points": int,
          "error": str | None,
        }
    """
    out = {
        "ok": False, "keyword": keyword,
        "trend_score": 0, "trend_avg": 0.0,
        "rising_pct": 0.0, "data_points": 0,
        "error": None,
    }
    client = _get_client()
    if client is None:
        out["error"] = "pytrends_unavailable"
        return out

    try:
        client.build_payload(
            kw_list=[keyword],
            cat=0,                # كل الفئات
            timeframe=timeframe,
            geo=geo,
            gprop="",             # web search (الافتراضي)
        )
        df = client.interest_over_time()
        if df is None or df.empty:
            out["error"] = "no_data"
            return out

        # العمود = اسم الـ keyword، نأخذ آخر قيمة + متوسط
        series = df[keyword]
        latest = int(series.iloc[-1])
        avg = float(series.mean())
        rising = ((latest - avg) / avg * 100.0) if avg > 0 else 0.0

        out.update({
            "ok": True,
            "trend_score": latest,
            "trend_avg": round(avg, 2),
            "rising_pct": round(rising, 1),
            "data_points": len(series),
        })
        return out
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return out


def fetch_related_queries(keyword: str, *, geo: str = "SA",
                           timeframe: str = "now 7-d") -> dict[str, Any]:
    """
    يجلب الـ related queries لـ keyword (top + rising).
    مفيد لاكتشاف صيغ بحث ناشئة يكتبها الناس فعلاً.

    Returns: {"ok": bool, "top": [...], "rising": [...], "error": str|None}
    """
    out = {"ok": False, "top": [], "rising": [], "error": None}
    client = _get_client()
    if client is None:
        out["error"] = "pytrends_unavailable"
        return out

    try:
        client.build_payload(
            kw_list=[keyword], cat=0,
            timeframe=timeframe, geo=geo, gprop="",
        )
        related = client.related_queries() or {}
        kw_data = related.get(keyword) or {}
        top_df = kw_data.get("top")
        rising_df = kw_data.get("rising")
        if top_df is not None and not top_df.empty:
            out["top"] = top_df.head(10).to_dict(orient="records")
        if rising_df is not None and not rising_df.empty:
            out["rising"] = rising_df.head(10).to_dict(orient="records")
        out["ok"] = True
        return out
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
        return out


def refresh_all_active_keywords(*, delay_between: float = 5.0) -> dict[str, int]:
    """
    يستدعيه الـ scheduler كل ساعة.
    يقرأ كل keyword نشط من seo_opportunity_keywords،
    يجلب درجة Trends، يحفظها.

    delay_between: ثوانٍ بين كل keyword لتفادي rate-limit (Google يحبّ ≥ 3s).
    """
    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context

    stats = {"checked": 0, "updated": 0, "failed": 0}

    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, keyword FROM seo_opportunity_keywords "
                "WHERE active = TRUE ORDER BY id"
            )
            rows = cur.fetchall()

        for row in rows:
            stats["checked"] += 1
            result = fetch_keyword_score(row["keyword"])
            with conn.cursor() as cur2:
                if result["ok"]:
                    cur2.execute(
                        """
                        UPDATE seo_opportunity_keywords
                        SET trend_score   = %s,
                            trend_avg     = %s,
                            rising_pct    = %s,
                            last_checked_at = NOW(),
                            last_error    = NULL
                        WHERE id = %s
                        """,
                        (result["trend_score"], result["trend_avg"],
                         result["rising_pct"], row["id"]),
                    )
                    stats["updated"] += 1
                else:
                    cur2.execute(
                        """
                        UPDATE seo_opportunity_keywords
                        SET last_checked_at = NOW(),
                            last_error    = %s
                        WHERE id = %s
                        """,
                        (result["error"], row["id"]),
                    )
                    stats["failed"] += 1
            # تأخير لتفادي 429 من Google
            if delay_between > 0 and stats["checked"] < len(rows):
                time.sleep(delay_between)

    _log.info("trends refresh cycle: %s", stats)
    return stats
