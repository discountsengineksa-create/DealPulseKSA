"""
لقطة أداء SEO اليومية — تجمع PageSpeed (جوال) + Search Console (آخر 28 يوم)
وتخزّنها في seo_perf_snapshots (صف لكل يوم). يستدعيها كرون يومي + زر يدوي.

يقرأ من البيئة (على خدمة DEALPULSEKSA حيث يعمل الكرون):
  PAGESPEED_API_KEY  — اختياري (بلا مفتاح = معدّل محدود)
  GSC_SA_JSON        — محتوى service account (JSON) لـ Search Console
  GSC_SITE           — رابط الخاصية (افتراضي www.dealpulseksa.com)
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from datetime import timedelta

import requests

from api.db import get_db_context

_log = logging.getLogger("dp.seo.snapshot")
SITE = os.getenv("GSC_SITE", "https://www.dealpulseksa.com/")


def _pagespeed_scores():
    """درجات PageSpeed (جوال) كـ (perf, seo, a11y, best) أو Nones عند الفشل."""
    params = [("url", SITE), ("strategy", "mobile")]
    for c in ("performance", "seo", "accessibility", "best-practices"):
        params.append(("category", c))
    key = os.getenv("PAGESPEED_API_KEY")
    if key:
        params.append(("key", key))
    r = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
                     params=params, timeout=70)
    cats = (r.json().get("lighthouseResult") or {}).get("categories") or {}

    def _s(k):
        v = (cats.get(k) or {}).get("score")
        return int(round(v * 100)) if v is not None else None
    return _s("performance"), _s("seo"), _s("accessibility"), _s("best-practices")


def _gsc_totals():
    """إجماليات Search Console لآخر 28 يوم: (clicks, impressions, ctr, position)."""
    raw = os.getenv("GSC_SA_JSON")
    if not raw:
        return (None, None, None, None)
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    svc = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end = datetime.date.today()
    start = end - timedelta(days=28)
    resp = svc.searchanalytics().query(
        siteUrl=SITE,
        body={"startDate": str(start), "endDate": str(end), "dimensions": [], "rowLimit": 1},
    ).execute()
    a = (resp.get("rows") or [{}])[0]
    return (int(a.get("clicks", 0)), int(a.get("impressions", 0)),
            round(float(a.get("ctr", 0)), 4), round(float(a.get("position", 0)), 2))


def capture_snapshot() -> dict:
    """يلتقط لقطة اليوم ويخزّنها (upsert على تاريخ اليوم)."""
    ps_error = gsc_error = None
    try:
        ps = _pagespeed_scores()
    except Exception as e:  # noqa: BLE001
        ps_error = f"{type(e).__name__}: {e}"
        _log.warning("pagespeed snapshot failed: %s", ps_error)
        ps = (None, None, None, None)
    try:
        g = _gsc_totals()
    except Exception as e:  # noqa: BLE001
        gsc_error = f"{type(e).__name__}: {e}"
        _log.warning("gsc snapshot failed: %s", gsc_error)
        g = (None, None, None, None)

    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO seo_perf_snapshots
                    (snapshot_date, ps_performance, ps_seo, ps_accessibility,
                     ps_best_practices, gsc_clicks, gsc_impressions, gsc_ctr, gsc_position)
                VALUES (CURRENT_DATE, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (snapshot_date) DO UPDATE SET
                    ps_performance    = EXCLUDED.ps_performance,
                    ps_seo            = EXCLUDED.ps_seo,
                    ps_accessibility  = EXCLUDED.ps_accessibility,
                    ps_best_practices = EXCLUDED.ps_best_practices,
                    gsc_clicks        = EXCLUDED.gsc_clicks,
                    gsc_impressions   = EXCLUDED.gsc_impressions,
                    gsc_ctr           = EXCLUDED.gsc_ctr,
                    gsc_position      = EXCLUDED.gsc_position
                """,
                (*ps, *g),
            )
        conn.commit()
    _log.info("seo snapshot captured: ps=%s gsc=%s", ps, g)
    return {"pagespeed": ps, "gsc": g, "ps_error": ps_error, "gsc_error": gsc_error}
