"""
تفصيل Search Console بالصفحة والاستعلام — ما تحتاجه الحملة ولا يعطيه الإجمالي.

`perf_snapshot.py` يخزّن إجماليات الموقع، فلا تعرف حملةٌ أداء **صفحتها المقصودة**
ولا الاستعلامات التي جلبتها. هذه الوحدة تسحب البُعدين وتخزّنهما في
`seo_gsc_pages` و`seo_gsc_queries` (migration 071)، فتقرأهما صفحة إدارة الحملات.

يقرأ من البيئة (نفس مفاتيح perf_snapshot — لا اعتماد جديد):
  GSC_SA_JSON — محتوى service account (JSON) لـ Search Console
  GSC_SITE    — رابط الخاصية (افتراضي https://www.dealpulseksa.com/)

⚠️ **قاعدة القراءة:** كل صفّ إجمالي **نافذة ٢٨ يوماً منتهية بـ`snapshot_date`**،
لا يوماً واحداً. **لا تُجمَع الصفوف** — تُقرأ آخر لقطة، والأقدم اتجاهٌ لا مجموع.
(جمعها ضخّم رقماً حقيقياً ١٧٫٣ ضعفاً قبل أن يُكشف.)

⚠️ وGSC يتأخّر يومين عادةً، فآخر لقطة تصف نافذة تنتهي قبل اليوم بيومين تقريباً.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from datetime import timedelta

from api.db import get_db_context

_log = logging.getLogger("dp.seo.gsc_detail")

SITE = os.getenv("GSC_SITE", "https://www.dealpulseksa.com/")
WINDOW_DAYS = 28          # نفس نافذة perf_snapshot كي تتطابق القراءتان
# ٥٠٠٠ لا ٥٠٠: GSC يرتّب الصفوف بالنقرات تنازلياً، وأغلب استعلاماتنا بصفر نقرة،
# فسقف ٥٠٠ كان يقتطع كل «مسافة الضربة» (مركز ٥–١٥ بظهور عالٍ وصفر نقرة) — وهي
# بالضبط ما نحتاج رؤيته للتحسين. GSC يسمح حتى ٢٥٬٠٠٠ صفّ/طلب.
ROW_LIMIT = 5000


def _service():
    """عميل Search Console من الـ service account، أو None بلا اعتمادات."""
    raw = os.getenv("GSC_SA_JSON")
    if not raw:
        return None
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    return build("searchconsole", "v1", credentials=creds, cache_discovery=False)


def _query_dimension(svc, dimension: str, start: datetime.date, end: datetime.date):
    """صفوف بُعد واحد (page أو query) لنافذة محدّدة."""
    resp = svc.searchanalytics().query(
        siteUrl=SITE,
        body={
            "startDate": str(start),
            "endDate": str(end),
            "dimensions": [dimension],
            "rowLimit": ROW_LIMIT,
        },
    ).execute()
    return resp.get("rows") or []


def capture_gsc_detail() -> dict:
    """
    يسحب أداء الصفحات والاستعلامات لآخر ٢٨ يوماً ويخزّنهما بلقطة اليوم.

    يعيد dict فيه عدد الصفوف المخزّنة لكل بُعد، أو سبب التخطّي. لا يرمي —
    الكرون اليومي لا يُسقط بقيّة دورته بسبب GSC.
    """
    svc = _service()
    if svc is None:
        _log.info("gsc detail skipped: GSC_SA_JSON غير مضبوط")
        return {"skipped": "no_credentials"}

    end = datetime.date.today()
    start = end - timedelta(days=WINDOW_DAYS)
    out = {"pages": 0, "queries": 0}

    try:
        pages = _query_dimension(svc, "page", start, end)
        queries = _query_dimension(svc, "query", start, end)
    except Exception as exc:                      # شبكة/صلاحيات — لا يُسقط الدورة
        _log.warning("gsc detail pull failed (non-fatal): %s", exc)
        return {"error": str(exc)[:200]}

    with get_db_context() as conn:
        with conn.cursor() as cur:
            for row in pages:
                cur.execute(
                    """
                    INSERT INTO seo_gsc_pages
                        (snapshot_date, page, clicks, impressions, ctr, position)
                    VALUES (CURRENT_DATE, %s, %s, %s, %s, %s)
                    ON CONFLICT (snapshot_date, page) DO UPDATE SET
                        clicks      = EXCLUDED.clicks,
                        impressions = EXCLUDED.impressions,
                        ctr         = EXCLUDED.ctr,
                        position    = EXCLUDED.position
                    """,
                    (row["keys"][0], int(row.get("clicks") or 0),
                     int(row.get("impressions") or 0),
                     row.get("ctr"), row.get("position")),
                )
                out["pages"] += 1

            for row in queries:
                cur.execute(
                    """
                    INSERT INTO seo_gsc_queries
                        (snapshot_date, query, clicks, impressions, ctr, position)
                    VALUES (CURRENT_DATE, %s, %s, %s, %s, %s)
                    ON CONFLICT (snapshot_date, query) DO UPDATE SET
                        clicks      = EXCLUDED.clicks,
                        impressions = EXCLUDED.impressions,
                        ctr         = EXCLUDED.ctr,
                        position    = EXCLUDED.position
                    """,
                    (row["keys"][0], int(row.get("clicks") or 0),
                     int(row.get("impressions") or 0),
                     row.get("ctr"), row.get("position")),
                )
                out["queries"] += 1
        conn.commit()

    try:
        out["landing_backfilled"] = backfill_landing_page_perf()
    except Exception as exc:
        _log.warning("landing-page perf backfill failed (non-fatal): %s", exc)

    _log.info("gsc detail captured: %s pages, %s queries, %s landing backfilled",
              out["pages"], out["queries"], out.get("landing_backfilled", 0))
    return out


def backfill_landing_page_perf() -> int:
    """
    حلقة التغذية الراجعة المفقودة: `seo_landing_pages.current_position` كانت **NULL
    للـ٢٠٠ صفحة** رغم أن الكرون يخزّن `seo_gsc_pages` يومياً — لأن لا شيء يربط
    البُعدين. هذا يطابق `/c/{slug}` من آخر لقطة GSC بسلاگ الصفحة ويكتب المركز
    والنقرات والظهور. بدونها المحرّك أعمى: لا يعرف أي صفحة `/c/` تُرتَّب وأيّها حِمل ميت.

    يعيد عدد الصفوف المحدَّثة.
    """
    from urllib.parse import unquote

    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT max(snapshot_date) FROM seo_gsc_pages")
            snap = cur.fetchone()[0]
            if snap is None:
                return 0
            cur.execute(
                "SELECT page, clicks, impressions, position FROM seo_gsc_pages "
                "WHERE snapshot_date = %s AND page LIKE %s",
                (snap, "%/c/%"),
            )
            by_slug: dict[str, tuple[int, int, float | None]] = {}
            for page, clicks, impressions, position in cur.fetchall():
                slug = unquote(page.rsplit("/c/", 1)[-1].split("?", 1)[0].split("#", 1)[0]).strip()
                if slug:
                    by_slug[slug] = (clicks or 0, impressions or 0, position)

            # صفر لكل الصفحات المنشورة أولاً (الغائبة عن GSC = صفر فعليّ، لا NULL)،
            # ثم اكتب الأرقام الحقيقية لمن ظهر. هكذا «صفر ظهور» يصبح إشارة صريحة.
            cur.execute(
                "UPDATE seo_landing_pages SET current_position = NULL, "
                "organic_clicks_7d = 0, organic_impressions_7d = 0 "
                "WHERE status = 'published'"
            )
            updated = 0
            for slug, (clicks, impressions, position) in by_slug.items():
                cur.execute(
                    "UPDATE seo_landing_pages SET current_position = %s, "
                    "organic_clicks_7d = %s, organic_impressions_7d = %s "
                    "WHERE slug = %s AND status = 'published'",
                    (round(position) if position is not None else None,
                     clicks, impressions, slug),
                )
                updated += cur.rowcount
        conn.commit()

    _log.info("landing-page perf backfill: %d /c/ pages matched to GSC", updated)
    return updated


def queries_for_page(page_url: str, days: int = WINDOW_DAYS, limit: int = 25):
    """
    استعلامات صفحة بعينها (نافذة `days`) — يُستدعى عند الطلب من صفحة الحملات،
    لأن الاستعلامات المخزَّنة يومياً على مستوى الموقع لا الصفحة.

    يعيد قائمة dicts أو [] بلا اعتمادات/عند الفشل — العرض لا يُسقط الصفحة.
    """
    svc = _service()
    if svc is None or not page_url:
        return []
    end = datetime.date.today()
    start = end - timedelta(days=days)
    try:
        resp = svc.searchanalytics().query(
            siteUrl=SITE,
            body={
                "startDate": str(start),
                "endDate": str(end),
                "dimensions": ["query"],
                "dimensionFilterGroups": [{
                    "filters": [{"dimension": "page", "operator": "equals", "expression": page_url}]
                }],
                "rowLimit": limit,
            },
        ).execute()
    except Exception as exc:
        _log.warning("gsc queries_for_page failed (non-fatal): %s", exc)
        return []
    return [
        {
            "query": r["keys"][0],
            "clicks": int(r.get("clicks") or 0),
            "impressions": int(r.get("impressions") or 0),
            "ctr": r.get("ctr"),
            "position": r.get("position"),
        }
        for r in (resp.get("rows") or [])
    ]
