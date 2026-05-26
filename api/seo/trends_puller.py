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


# ─── urllib3 compat shim ──────────────────────────────────────────────────────
# pytrends 4.9.2 يستخدم urllib3.Retry(method_whitelist=...) — وهذا اسم قديم
# تم حذفه في urllib3 ≥ 2.0 (الاسم الجديد: allowed_methods). Railway يثبّت
# urllib3 ≥ 2.0 افتراضياً، فيحدث TypeError عند أول استدعاء.
# الحل: monkey-patch Retry.__init__ ليقبل الاسم القديم كـ alias.
def _install_urllib3_compat_shim() -> None:
    try:
        import urllib3.util.retry as _retry_mod
        _orig_init = _retry_mod.Retry.__init__
        if getattr(_orig_init, "_dp_patched", False):
            return  # مُطبَّق مسبقاً
        def _patched_init(self, *args, **kwargs):
            if "method_whitelist" in kwargs and "allowed_methods" not in kwargs:
                kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
            return _orig_init(self, *args, **kwargs)
        _patched_init._dp_patched = True  # type: ignore[attr-defined]
        _retry_mod.Retry.__init__ = _patched_init
    except Exception as exc:
        _log.warning("urllib3 compat shim failed: %s", exc)


_install_urllib3_compat_shim()

# pytrends يبني client داخلياً عند الاستدعاء — نُنشئ instance واحد يُعاد استخدامه
# مع cookies session لتقليل rate-limit
_pytrends_client = None


_last_init_error: str | None = None  # تشخيص: آخر سبب فشل init


def _get_client():
    """يُنشئ pytrends client بـ lazy init. يرجع None لو الـ import فشل."""
    global _pytrends_client, _last_init_error
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
        _last_init_error = None
        return _pytrends_client
    except Exception as exc:
        _last_init_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        _log.error("pytrends import/init failed: %s", _last_init_error)
        return None


def get_init_status() -> dict:
    """يرجع حالة الاستيراد لـ pytrends (للتشخيص فقط)."""
    import sys
    out = {
        "pytrends_installed": "pytrends" in sys.modules,
        "client_active": _pytrends_client is not None,
        "last_init_error": _last_init_error,
    }
    # حاول import مباشر للتأكد
    try:
        import pytrends  # noqa: F401
        from pytrends.request import TrendReq  # noqa: F401
        out["import_test"] = "ok"
        out["pytrends_version"] = getattr(pytrends, "__version__", "unknown")
    except Exception as exc:
        out["import_test"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return out


def fetch_keyword_score(keyword: str, *, geo: str = "SA",
                         timeframe: str = "today 3-m",
                         with_related: bool = True) -> dict[str, Any]:
    """
    يجلب درجة الاهتمام + (اختيارياً) الكلمات المرتبطة لـ keyword في منطقة معيّنة.

    Args:
        keyword: الكلمة المستهدفة (مثلاً "كود خصم نون")
        geo: ISO country code ("SA" للسعودية، "" للعالم)
        timeframe: نطاق Google Trends. الافتراضي 3 أشهر لإعطاء بيانات
            كافية للكلمات النيش. الخيارات: "now 1-d", "now 7-d",
            "today 1-m", "today 3-m", "today 12-m", "today 5-y"
        with_related: لو True، يجلب أيضاً top + rising related queries

    Returns:
        {
          "ok": bool,
          "keyword": str,
          "trend_score": int (0-100, آخر نقطة في الـ timeseries),
          "trend_avg": float (متوسط الفترة كاملة),
          "trend_peak": int (أعلى نقطة في الفترة),
          "rising_pct": float (% تغير آخر نقطة عن متوسط الفترة),
          "data_points": int,
          "related_top":    [{"query": str, "value": int}, ...]  # حتى 10
          "related_rising": [{"query": str, "value": int|str}, ...]  # حتى 10
          "error": str | None,
        }
    """
    out: dict[str, Any] = {
        "ok": False, "keyword": keyword,
        "trend_score": 0, "trend_avg": 0.0, "trend_peak": 0,
        "rising_pct": 0.0, "data_points": 0,
        "related_top": [], "related_rising": [],
        "error": None,
    }

    # ─── المصدر #1: Google Suggest (مستقل، مجاني، مستقر — يعمل دائماً) ─────────
    # نشغّله أولاً ودائماً — مستقل عن pytrends، فحتى لو Google يحجب Trends
    # عن Railway IPs، الـ user يحصل على اقتراحات حقيقية بنقرة واحدة.
    if with_related:
        try:
            suggestions = fetch_google_suggestions(keyword, hl="ar", gl="sa")
            if suggestions:
                out["related_top"] = suggestions
                # علامة جزئية: حتى لو pytrends فشل، الاقتراحات نجحت
                out["ok"] = True
        except Exception as sg_exc:
            _log.warning("suggest primary failed for '%s': %s",
                         keyword[:50], str(sg_exc)[:200])

    # ─── المصدر #2: pytrends (الـ trend score — قد يفشل بسبب rate-limit) ──────
    client = _get_client()
    if client is None:
        if not out["ok"]:
            out["error"] = "pytrends_unavailable_no_suggestions"
        return out

    try:
        client.build_payload(
            kw_list=[keyword],
            cat=0,
            timeframe=timeframe,
            geo=geo,
            gprop="",
        )
        df = client.interest_over_time()
        if df is None or df.empty:
            # ليس فشلاً — لو عندنا اقتراحات نُرجع ok=True مع تنبيه فقط
            if not out["ok"]:
                out["error"] = "no_trends_data"
            return out

        series = df[keyword]
        latest = int(series.iloc[-1])
        avg = float(series.mean())
        peak = int(series.max())
        rising = ((latest - avg) / avg * 100.0) if avg > 0 else 0.0

        out.update({
            "ok": True,
            "trend_score": latest,
            "trend_avg": round(avg, 2),
            "trend_peak": peak,
            "rising_pct": round(rising, 1),
            "data_points": len(series),
        })

        # محاولة إضافة related queries من pytrends لاحقاً (قد تُثري قائمة Suggest)
        if with_related:
            try:
                related = client.related_queries() or {}
                kw_data = related.get(keyword) or {}
                rising_df = kw_data.get("rising")
                if rising_df is not None and not rising_df.empty:
                    # rising من pytrends أهم (مع نسب %) — Suggest لا يعطي rising
                    out["related_rising"] = rising_df.head(10).to_dict(orient="records")
                # لو pytrends أعطى top أغنى من Suggest، استبدلها
                top_df = kw_data.get("top")
                if top_df is not None and not top_df.empty:
                    pt_top = top_df.head(10).to_dict(orient="records")
                    if len(pt_top) > len(out["related_top"]):
                        out["related_top"] = pt_top
            except Exception as rel_exc:
                _log.warning("pytrends related_queries failed for '%s': %s",
                             keyword[:50], str(rel_exc)[:200])
        return out
    except Exception as exc:
        # pytrends فشل (rate-limit، شبكة، إلخ) — لكن لو عندنا اقتراحات Suggest
        # نُعتبر النتيجة جزئية ناجحة بدل فشل كامل.
        err_msg = f"{type(exc).__name__}: {str(exc)[:200]}"
        if out["related_top"]:
            out["error"] = f"trends_unavailable: {err_msg}"
            # ok يبقى True لأن عندنا اقتراحات
        else:
            out["error"] = err_msg
        return out


def fetch_google_suggestions(keyword: str, *, hl: str = "ar",
                              gl: str = "sa") -> list[dict[str, Any]]:
    """
    يجلب اقتراحات Google Autocomplete (نفس ما يظهر في صندوق بحث Google).
    هذا مكمّل لـ pytrends related_queries (الذي صار غير موثوق منذ تغيير
    Google لـ API). الـ Suggest API:
      • مجاني وبدون auth
      • يرجع 10 اقتراحات حقيقية يكتبها الناس فعلاً
      • أسرع وأكثر استقراراً من pytrends

    Returns: list of {"query": str, "value": "suggest"}
    """
    import requests as _rq
    try:
        url = "https://suggestqueries.google.com/complete/search"
        params = {
            "client": "firefox",   # يرجع JSON نظيف
            "q":  keyword,
            "hl": hl,              # لغة الواجهة
            "gl": gl,              # بلد الزائر (SA)
        }
        r = _rq.get(url, params=params, timeout=8,
                    headers={"User-Agent": "DealPulseKSA-Opportunities/1.0"})
        if r.status_code != 200:
            return []
        data = r.json()
        # الصيغة: [query, [suggestion1, suggestion2, ...]]
        if not isinstance(data, list) or len(data) < 2:
            return []
        suggestions = data[1] or []
        kw_lower = keyword.lower().strip()
        out = []
        for s in suggestions[:10]:
            s_text = str(s or "").strip()
            if not s_text or s_text.lower() == kw_lower:
                continue
            out.append({"query": s_text, "value": "suggest"})
        return out
    except Exception as exc:
        _log.warning("google_suggest failed for '%s': %s",
                     keyword[:50], str(exc)[:200])
        return []


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
    يجلب درجة Trends + related queries، يحفظها.

    delay_between: ثوانٍ بين كل keyword لتفادي rate-limit (Google يحبّ ≥ 3s).
    """
    import json as _json
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
                        SET trend_score    = %s,
                            trend_avg      = %s,
                            trend_peak     = %s,
                            rising_pct     = %s,
                            related_top    = %s::jsonb,
                            related_rising = %s::jsonb,
                            last_checked_at = NOW(),
                            last_error     = NULL
                        WHERE id = %s
                        """,
                        (result["trend_score"], result["trend_avg"],
                         result.get("trend_peak", 0),
                         result["rising_pct"],
                         _json.dumps(result.get("related_top") or []),
                         _json.dumps(result.get("related_rising") or []),
                         row["id"]),
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
