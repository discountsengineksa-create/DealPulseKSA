"""
Search-engine notifier — يُستدعى عند نشر صفحة هبوط.

  1. يطلب من الموقع (Next.js) إعادة تحقّق الكاش: POST {SITE_URL}/api/revalidate
  2. يخطر IndexNow (Bing/Yandex): POST {SITE_URL}/api/indexnow
  3. يسجّل المحاولة في seo_index_submissions.

كله best-effort ومحكوم بالبيئة — لو REVALIDATE_SECRET غير مضبوط يُتخطّى
بهدوء (لا يفشل النشر). Google Indexing API (service account) مؤجّل.

ملاحظة: مسار صفحة الهبوط على الموقع قابل للضبط عبر SEO_PAGE_PATH
(افتراضي /c/{slug}) — يلزم إنشاء هذا الـ route في dealpulseksa-web لاحقاً.
"""
from __future__ import annotations

import logging
import os

from api.db import get_db_context

_log = logging.getLogger("dp.seo.indexer")

SITE_URL = os.getenv("SITE_URL", "https://dealpulseksa.com").rstrip("/")
SEO_PAGE_PATH = os.getenv("SEO_PAGE_PATH", "/c/{slug}")


def _page_path(slug: str) -> str:
    return SEO_PAGE_PATH.format(slug=slug)


def _record(landing_page_id: int, provider: str, code: int | None, body: str | None) -> None:
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO seo_index_submissions
                        (landing_page_id, provider, response_code, response_json)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (landing_page_id, provider, code,
                     None if body is None else __import__("json").dumps({"resp": body[:500]})),
                )
    except Exception as exc:
        _log.warning("seo_index_submissions insert failed: %s", exc)


def submit_page(*, landing_page_id: int, slug: str) -> dict:
    """يخطر الموقع + IndexNow لصفحة منشورة. يرجّع ملخّص النتائج."""
    secret = os.getenv("REVALIDATE_SECRET")
    if not secret:
        _log.info("REVALIDATE_SECRET unset — skipping index submission for %s", slug)
        return {"skipped": True, "reason": "no_revalidate_secret"}

    import requests  # متوفّر أصلاً في المشروع

    path = _page_path(slug)
    full_url = f"{SITE_URL}{path}"
    out: dict = {"slug": slug, "url": full_url}

    # 1) revalidate cache على الموقع
    try:
        r = requests.post(
            f"{SITE_URL}/api/revalidate",
            json={"secret": secret, "paths": [path]},
            timeout=8,
        )
        out["revalidate_code"] = r.status_code
    except Exception as exc:
        out["revalidate_error"] = str(exc)[:200]

    # 2) IndexNow
    try:
        r = requests.post(
            f"{SITE_URL}/api/indexnow",
            json={"secret": secret, "urls": [full_url]},
            timeout=8,
        )
        out["indexnow_code"] = r.status_code
        _record(landing_page_id, "indexnow_bing", r.status_code, getattr(r, "text", None))
    except Exception as exc:
        out["indexnow_error"] = str(exc)[:200]
        _record(landing_page_id, "indexnow_bing", None, str(exc))

    _log.info("index submit %s → %s", slug, out)
    return out
