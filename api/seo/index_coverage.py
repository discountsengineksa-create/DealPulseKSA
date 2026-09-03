"""
تغطية فهرسة Google لكل رابط — تشخيص من Search Console (migration 073).

صفحة «🔎 الفهرسة» في الداشبورد تشتقّ «المعلّقة» = (روابط sitemap) ناقص
(seo_index_queue اليدوي). أغلب «المعلّقة» مفهرَس أصلاً — هذه الوحدة تسحب حالة
Google الحقيقية فتُشطب المفهرَسة تلقائياً ويتحوّل الباقي إلى worklist مصنّفة بالسبب.

مصدران يملآن `seo_index_coverage`:
  • reconcile_from_impressions() — أي رابط له ≥1 انطباع في GSC خلال 16 شهراً ⇒
    مفهرَس قطعاً (نداء API واحد رخيص، يصلح للكرون اليومي).
  • inspect_urls()             — URL Inspection API لكل رابط لم يظهر بانطباع:
    يعطي coverageState الحقيقي. حصة 2000/يوم/خاصية — يدوي من الداشبورد.

يقرأ نفس بيئة `gsc_detail` (GSC_SA_JSON / GSC_SITE) — لا اعتماد جديد.
"""
from __future__ import annotations

import datetime
import logging
import re
import time
from urllib.parse import unquote

from api.db import get_db_context
from api.seo.gsc_detail import SITE, _service

_log = logging.getLogger("dp.seo.index_coverage")

SITEMAP_BASE = SITE.rstrip("/")
IMPRESSIONS_WINDOW_DAYS = 470          # < 16 شهراً بهامش أمان من رفض حدّ الـAPI
INSPECT_RECHECK_DAYS = 7               # لا تُعِد فحص رابط فُحص خلال أسبوع
_ROW_LIMIT = 25000


# ═══════════════════════════════════════════════════════════════════════════
#  أدوات مشتركة
# ═══════════════════════════════════════════════════════════════════════════
def _norm(url: str) -> str:
    """تطبيع رابط للمطابقة: unquote + إسقاط ?query/#frag + إزالة / الأخيرة."""
    u = unquote((url or "").strip())
    u = u.split("?", 1)[0].split("#", 1)[0]
    return u.rstrip("/")


def fetch_sitemap_urls(base: str | None = None) -> list[str]:
    """كل روابط sitemap الحيّ (يتبع sitemap index إن وُجد). مطبَّعة، بترتيب الظهور."""
    import requests

    base = (base or SITEMAP_BASE).rstrip("/")
    order: list[str] = []
    seen: set[str] = set()
    queue = [f"{base}/sitemap.xml"]
    done: set[str] = set()
    while queue:
        sm = queue.pop(0)
        if sm in done:
            continue
        done.add(sm)
        try:
            txt = requests.get(sm, timeout=25,
                               headers={"User-Agent": "Mozilla/5.0 (DealPulse indexer)"}).text
        except Exception as exc:
            _log.warning("sitemap fetch failed %s: %s", sm, exc)
            continue
        locs = [m.strip() for m in re.findall(r"<loc>\s*(.*?)\s*</loc>", txt, re.I | re.S)]
        if "<sitemapindex" in txt.lower():
            queue.extend(locs)
            continue
        for u in locs:
            n = _norm(u)
            if n not in seen:
                seen.add(n)
                order.append(n)
    return order


def _verdict_from_state(state: str | None) -> tuple[str, bool]:
    """coverageState الخام → (verdict مُجمَّع، is_indexed)."""
    if not state:
        return "unknown", False
    s = state.lower()
    if "unknown to google" in s:
        return "unknown", False
    if "discovered" in s and "not indexed" in s:
        return "discovered", False
    if "crawled" in s and "not indexed" in s:
        return "crawled_not_indexed", False
    if "indexed" in s and "not indexed" not in s:
        return "indexed", True
    return "excluded_other", False


# ═══════════════════════════════════════════════════════════════════════════
#  كتابة seo_index_coverage + seo_index_queue
# ═══════════════════════════════════════════════════════════════════════════
def _upsert_coverage(cur, url: str, coverage_state: str | None,
                     verdict: str, is_indexed: bool, source: str) -> None:
    cur.execute(
        """
        INSERT INTO seo_index_coverage
            (url, coverage_state, verdict, is_indexed, last_source, checked_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (url) DO UPDATE SET
            coverage_state = EXCLUDED.coverage_state,
            verdict        = EXCLUDED.verdict,
            is_indexed     = EXCLUDED.is_indexed,
            last_source    = EXCLUDED.last_source,
            checked_at     = NOW()
        """,
        (url, coverage_state, verdict, is_indexed, source),
    )


def _mark_queue_indexed(cur, urls: list[str]) -> int:
    """يُدرج روابط مفهرَسة في seo_index_queue كـ('indexed','gsc'). لا يمسّ صفوف المالك
    (ON CONFLICT DO NOTHING — أي 'indexed'/'ignored' يدوي يبقى كما هو). يعيد عدد الجدد."""
    if not urls:
        return 0
    cur.execute("SELECT url FROM seo_index_queue")
    existing = {r[0] for r in cur.fetchall()}
    fresh = [u for u in urls if u not in existing]
    for u in fresh:
        cur.execute(
            "INSERT INTO seo_index_queue (url, status, source) "
            "VALUES (%s, 'indexed', 'gsc') ON CONFLICT (url) DO NOTHING",
            (u,),
        )
    return len(fresh)


# ═══════════════════════════════════════════════════════════════════════════
#  المصدر ١ — الانطباعات (رخيص، للكرون + زر «اسحب المفهرَس»)
# ═══════════════════════════════════════════════════════════════════════════
def reconcile_from_impressions() -> dict:
    """
    كل صفحة لها ≥1 انطباع في GSC خلال 16 شهراً وموجودة في sitemap ⇒ مفهرَسة قطعاً.
    تُكتب في seo_index_coverage (verdict='indexed') وتُشطب من «المعلّقة» عبر seo_index_queue.

    يعيد dict بالإحصاء، أو {"skipped": ...} بلا اعتمادات.
    """
    svc = _service()
    if svc is None:
        _log.info("index-coverage impressions skipped: GSC_SA_JSON غير مضبوط")
        return {"skipped": "no_credentials"}

    end = datetime.date.today()
    start = end - datetime.timedelta(days=IMPRESSIONS_WINDOW_DAYS)

    rows: list[dict] = []
    start_row = 0
    try:
        while True:
            resp = svc.searchanalytics().query(
                siteUrl=SITE,
                body={
                    "startDate": str(start),
                    "endDate": str(end),
                    "dimensions": ["page"],
                    "rowLimit": _ROW_LIMIT,
                    "startRow": start_row,
                },
            ).execute()
            batch = resp.get("rows") or []
            rows.extend(batch)
            if len(batch) < _ROW_LIMIT:
                break
            start_row += len(batch)
    except Exception as exc:
        _log.warning("index-coverage impressions pull failed (non-fatal): %s", exc)
        return {"error": str(exc)[:200]}

    sitemap = set(fetch_sitemap_urls())
    seen_pages = {_norm(r["keys"][0]) for r in rows}
    indexed = sorted(seen_pages & sitemap)

    with get_db_context() as conn:
        with conn.cursor() as cur:
            for u in indexed:
                _upsert_coverage(cur, u, "Impression in last 16 months",
                                 "indexed", True, "impressions")
            newly_marked = _mark_queue_indexed(cur, indexed)
        conn.commit()

    out = {
        "gsc_pages": len(seen_pages),
        "matched_sitemap": len(indexed),
        "newly_marked": newly_marked,
        "stale_not_in_sitemap": len(seen_pages - sitemap),
    }
    _log.info("index-coverage impressions: %s", out)
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  المصدر ٢ — URL Inspection (حصة 2000/يوم، يدوي من الداشبورد)
# ═══════════════════════════════════════════════════════════════════════════
def urls_needing_inspection(sitemap: list[str] | None = None) -> list[str]:
    """
    worklist الفحص = روابط sitemap ناقص (seo_index_queue) ناقص (coverage.is_indexed)
    ناقص (ما فُحص عبر inspection خلال INSPECT_RECHECK_DAYS). مرتّبة: الأولوية للمجهول/المكتشف
    ثم غير المفحوص، وأخيراً «زُحف ورُفض».

    `sitemap` اختياري — مرّره لتفادي جلب sitemap ثانيةً (الداشبورد يخزّنه للجلسة).
    """
    sitemap = sitemap or fetch_sitemap_urls()
    order = {u: i for i, u in enumerate(sitemap)}
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT url FROM seo_index_queue")
            acted = {r[0] for r in cur.fetchall()}
            cur.execute(
                "SELECT url, verdict, is_indexed, last_source, checked_at "
                "FROM seo_index_coverage"
            )
            cov = {r[0]: r for r in cur.fetchall()}

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=INSPECT_RECHECK_DAYS)
    rank = {"unknown": 0, "discovered": 1, "excluded_other": 3, "crawled_not_indexed": 4}

    todo: list[str] = []
    for u in sitemap:
        if u in acted:
            continue
        row = cov.get(u)
        if row and row[2]:                       # is_indexed
            continue
        if row and row[3] == "inspection" and row[4] and row[4] > cutoff:
            continue                             # فُحص حديثاً
        todo.append(u)

    todo.sort(key=lambda u: (rank.get(cov[u][1], 2) if u in cov else 2, order.get(u, 1 << 30)))
    return todo


def inspect_urls(urls: list[str]) -> dict:
    """
    يفحص القائمة المعطاة عبر URL Inspection API، يكتب كل رابط فور فحصه (قابل للاستئناف).
    الداشبورد يقسّمها دفعات ويعرض progress. يعيد إحصاء verdicts + الأخطاء.
    """
    svc = _service()
    if svc is None:
        return {"skipped": "no_credentials"}

    by_verdict: dict[str, int] = {}
    errors = 0
    checked = 0

    for url in urls:
        try:
            resp = svc.urlInspection().index().inspect(
                body={"inspectionUrl": url, "siteUrl": SITE}
            ).execute()
            isr = (resp.get("inspectionResult") or {}).get("indexStatusResult") or {}
            state = isr.get("coverageState")
            verdict, is_indexed = _verdict_from_state(state)
        except Exception as exc:
            errors += 1
            _log.warning("urlInspection failed %s: %s", url, str(exc)[:160])
            time.sleep(0.3)
            continue

        with get_db_context() as conn:
            with conn.cursor() as cur:
                _upsert_coverage(cur, url, state, verdict, is_indexed, "inspection")
                if is_indexed:
                    _mark_queue_indexed(cur, [url])
            conn.commit()

        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1
        checked += 1
        time.sleep(0.12)

    out = {"checked": checked, "errors": errors, "by_verdict": by_verdict}
    _log.info("index-coverage inspection: %s", out)
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  قراءة — للداشبورد
# ═══════════════════════════════════════════════════════════════════════════
def coverage_map() -> dict[str, dict]:
    """url → {verdict, coverage_state, is_indexed, last_source} لكل ما في seo_index_coverage."""
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT url, verdict, coverage_state, is_indexed, last_source "
                "FROM seo_index_coverage"
            )
            return {
                r[0]: {"verdict": r[1], "coverage_state": r[2],
                       "is_indexed": r[3], "last_source": r[4]}
                for r in cur.fetchall()
            }
