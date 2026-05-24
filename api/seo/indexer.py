"""
Search-engine notifier — يُستدعى عند نشر صفحة هبوط.

  1. revalidate cache على الموقع: POST {SITE_URL}/api/revalidate
  2. IndexNow (Bing/Yandex):     POST {SITE_URL}/api/indexnow
  3. Google Indexing API:        POST indexing.googleapis.com (لو الاعتماد متاح)
  4. تسجيل كل المحاولات في seo_index_submissions.

كله best-effort ومحكوم بمتغيرات البيئة. لو أي مكوّن غير مهيأ يُتخطّى بهدوء
بلا فشل النشر.

متغيرات البيئة:
  SITE_URL                              (default: https://dealpulseksa.com)
  SEO_PAGE_PATH                          (default: /c/{slug})
  REVALIDATE_SECRET                      (مطلوب لـ revalidate + IndexNow)
  GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON   (مطلوب لـ Google Indexing — يحتوي JSON كامل)

ملاحظة: Google Indexing API مخصّص رسمياً للـ JobPosting / BroadcastEvent،
لكنه يعمل عملياً لكل URL ويُعطي إشارة فهرسة قوية. استخدامه آمن للـ landing
pages الكوبونية إذا التزمت بحدود الـ quota (200 req/day افتراضياً).
"""
from __future__ import annotations

import json as _json
import logging
import os

from api.db import get_db_context

_log = logging.getLogger("dp.seo.indexer")

SITE_URL = os.getenv("SITE_URL", "https://dealpulseksa.com").rstrip("/")
SEO_PAGE_PATH = os.getenv("SEO_PAGE_PATH", "/c/{slug}")
GOOGLE_SA_JSON_RAW = os.getenv("GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON", "")


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
                     None if body is None else _json.dumps({"resp": body[:500]})),
                )
    except Exception as exc:
        _log.warning("seo_index_submissions insert failed: %s", exc)


# ─── Google Indexing API ─────────────────────────────────────────────────────
_google_token_cache: dict = {"token": None, "exp": 0}


def _get_google_access_token() -> str | None:
    """
    يحصل على OAuth2 access token من service account JSON.
    يستخدم cache (الـ token صالح ساعة كاملة).

    يرجّع None لو الاعتماد غير مهيأ أو فشل التوقيع.
    """
    if not GOOGLE_SA_JSON_RAW:
        return None

    import time as _time
    now = _time.time()
    cached = _google_token_cache
    if cached["token"] and cached["exp"] > now + 60:
        return cached["token"]

    try:
        # نستورد google-auth lazily — لا نضيف dependency إن لم تُستخدم الميزة
        from google.oauth2 import service_account  # type: ignore[import-untyped]
        import google.auth.transport.requests as _gt  # type: ignore[import-untyped]
    except ImportError:
        _log.warning(
            "google-auth library not installed — Google Indexing disabled. "
            "Install with: pip install google-auth"
        )
        return None

    try:
        sa_info = _json.loads(GOOGLE_SA_JSON_RAW)
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/indexing"]
        )
        creds.refresh(_gt.Request())
        _google_token_cache["token"] = creds.token
        _google_token_cache["exp"] = now + 3500  # ~ ساعة
        return creds.token
    except Exception as exc:
        _log.error("Google Indexing token fetch failed: %s", str(exc)[:200])
        return None


def _submit_to_google(landing_page_id: int, full_url: str, out: dict) -> None:
    """يخطر Google Indexing API بصفحة جديدة/محدّثة."""
    token = _get_google_access_token()
    if not token:
        out["google_skipped"] = "no_credentials_or_lib"
        return

    import requests
    try:
        r = requests.post(
            "https://indexing.googleapis.com/v3/urlNotifications:publish",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"url": full_url, "type": "URL_UPDATED"},
            timeout=10,
        )
        out["google_code"] = r.status_code
        _record(landing_page_id, "google_indexing_api", r.status_code, r.text)
        if r.status_code >= 400:
            _log.warning("Google Indexing %s: %s", r.status_code, r.text[:200])
    except Exception as exc:
        out["google_error"] = str(exc)[:200]
        _record(landing_page_id, "google_indexing_api", None, str(exc))


def _submit_to_indexnow(landing_page_id: int, full_url: str, secret: str, out: dict) -> None:
    """يخطر Bing/Yandex IndexNow عبر hook على الموقع."""
    import requests
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


def submit_page(*, landing_page_id: int, slug: str) -> dict:
    """
    يخطر كل محركات البحث المتاحة لصفحة منشورة.
    يرجّع ملخّصاً بحالة كل محرّك (revalidate, indexnow_bing, google_indexing_api).
    """
    path = _page_path(slug)
    full_url = f"{SITE_URL}{path}"
    out: dict = {"slug": slug, "url": full_url}

    import requests

    # 1) revalidate cache على الموقع (لو SECRET متاح)
    secret = os.getenv("REVALIDATE_SECRET")
    if secret:
        try:
            r = requests.post(
                f"{SITE_URL}/api/revalidate",
                json={"secret": secret, "paths": [path]},
                timeout=8,
            )
            out["revalidate_code"] = r.status_code
        except Exception as exc:
            out["revalidate_error"] = str(exc)[:200]

        # 2) IndexNow (يحتاج نفس secret)
        _submit_to_indexnow(landing_page_id, full_url, secret, out)
    else:
        out["revalidate_skipped"] = "no_secret"
        out["indexnow_skipped"] = "no_secret"

    # 3) Google Indexing API — مستقل عن REVALIDATE_SECRET
    _submit_to_google(landing_page_id, full_url, out)

    _log.info("index submit %s → %s", slug, out)
    return out
