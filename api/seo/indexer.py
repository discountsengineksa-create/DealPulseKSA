"""
Search-engine notifier — يُستدعى عند نشر صفحة هبوط.

تسلسل الإخطار (best-effort، فشل أيّ خطوة لا يكسر الباقي):

  1. revalidate cache على الـ Next.js: POST {SITE_URL}/api/revalidate
  2. IndexNow متعدد المحركات (Bing+Yandex+Naver) — POST مباشر للـ endpoints
     الرسمية (لا يمر عبر الموقع، أسرع وأكثر موثوقية)
  3. Google Indexing API — لو الاعتمادات موجودة + ownership متحقق
  4. كل المحاولات تُسجَّل في seo_index_submissions

متغيرات البيئة:
  SITE_URL                              (default: https://dealpulseksa.com)
  SEO_PAGE_PATH                          (default: /c/{slug})
  REVALIDATE_SECRET                      (مطلوب لـ Next.js revalidate)
  INDEXNOW_KEY                           (مفتاح IndexNow — انظر https://indexnow.org)
  INDEXNOW_KEY_LOCATION                  (URL يحتوي ملف المفتاح، افتراضي {SITE_URL}/{INDEXNOW_KEY}.txt)
  GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON   (JSON كامل لـ service account)

ملاحظة مهمة عن Google Indexing API:
  - Google رسمياً يدعم JobPosting و BroadcastEvent فقط، لكنه يقبل أي URL.
  - يتطلب أن يكون الـ service account "Owner" على الـ property في Search Console.
  - Domain properties لا تقبل service account كـ Owner من واجهة GSC (قيد أمني).
  - الحل: تحقق ownership عبر **DNS TXT record** أو **HTML file verification**
    (أسهل وأكثر استقراراً). انظر دالة diagnose_google_setup() أدناه.

ملاحظة عن IndexNow:
  - مفتوح ومجاني. Bing/Yandex/Naver/Seznam كلهم يقبلونه.
  - يتطلب فقط ملف مفتاح مستضاف على دومينك (للتحقق من الملكية).
  - مفعّل افتراضياً لكل المحركات الكبرى الـ4.
"""
from __future__ import annotations

import json as _json
import logging
import os
from typing import Any

from api.db import get_db_context

_log = logging.getLogger("dp.seo.indexer")

SITE_URL = os.getenv("SITE_URL", "https://www.dealpulseksa.com").rstrip("/")
SEO_PAGE_PATH = os.getenv("SEO_PAGE_PATH", "/c/{slug}")
GOOGLE_SA_JSON_RAW = os.getenv("GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON", "")
INDEXNOW_KEY = os.getenv("INDEXNOW_KEY", "").strip()
INDEXNOW_KEY_LOCATION = os.getenv("INDEXNOW_KEY_LOCATION", "").strip()


# ─── IndexNow endpoints (open protocol — same payload across engines) ──────
INDEXNOW_ENGINES = [
    ("indexnow_bing",   "https://www.bing.com/indexnow"),
    ("indexnow_yandex", "https://yandex.com/indexnow"),
    ("indexnow_naver",  "https://searchadvisor.naver.com/indexnow"),
    ("indexnow_seznam", "https://search.seznam.cz/indexnow"),
]


# ─── Helpers ────────────────────────────────────────────────────────────────
def _page_path(slug: str) -> str:
    return SEO_PAGE_PATH.format(slug=slug)


def _record(landing_page_id: int, provider: str, code: int | None,
            body: str | None) -> None:
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
                     None if body is None
                     else _json.dumps({"resp": str(body)[:500]})),
                )
    except Exception as exc:
        _log.warning("seo_index_submissions insert failed: %s", exc)


# ═══════════════════════════════════════════════════════════════════════════
#  Google Indexing API
# ═══════════════════════════════════════════════════════════════════════════
_google_token_cache: dict[str, Any] = {"token": None, "exp": 0}


def _get_google_access_token() -> str | None:
    """يحصل على OAuth2 token من service account JSON (مع cache ساعة)."""
    if not GOOGLE_SA_JSON_RAW:
        return None

    import time as _time
    now = _time.time()
    cached = _google_token_cache
    if cached["token"] and cached["exp"] > now + 60:
        return cached["token"]

    try:
        from google.oauth2 import service_account  # type: ignore[import-untyped]
        import google.auth.transport.requests as _gt  # type: ignore[import-untyped]
    except ImportError:
        _log.warning("google-auth not installed — Google Indexing disabled. "
                     "Add to requirements: google-auth==2.40.1")
        return None

    try:
        sa_info = _json.loads(GOOGLE_SA_JSON_RAW)
        creds = service_account.Credentials.from_service_account_info(
            sa_info, scopes=["https://www.googleapis.com/auth/indexing"]
        )
        creds.refresh(_gt.Request())
        _google_token_cache["token"] = creds.token
        _google_token_cache["exp"] = now + 3500
        return creds.token
    except Exception as exc:
        _log.error("Google Indexing token fetch failed: %s", str(exc)[:200])
        return None


def _submit_to_google(landing_page_id: int, full_url: str, out: dict) -> None:
    """
    يخطر Google. يفسّر أكواد الخطأ الشائعة بوضوح حتى يفهم الـ ops
    سبب الفشل (مفتاح خطأ vs ownership غير محقق vs quota مستنفد).
    """
    token = _get_google_access_token()
    if not token:
        out["google"] = {"skipped": "no_credentials_or_lib"}
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
        code = r.status_code
        body = r.text[:400]

        # ترجمة الأكواد الشائعة لرسائل مفيدة
        if code == 200:
            diagnosis = "ok"
        elif code == 403:
            if "Permission denied" in body or "permission" in body.lower():
                diagnosis = (
                    "FORBIDDEN — service account ليس owner على الـ property في "
                    "Search Console. الحل: ضِف رابط DNS TXT verification "
                    "(راجع diagnose_google_setup) أو استخدم HTML file."
                )
            else:
                diagnosis = f"forbidden: {body[:120]}"
        elif code == 429:
            diagnosis = "quota_exceeded — Google يحدّد ~200 طلب/يوم/مفتاح"
        elif code == 404:
            diagnosis = "url_not_found_on_site (تأكد من نشر الصفحة على الموقع أولاً)"
        elif code == 401:
            diagnosis = "auth_failed — مفتاح JSON غير صالح أو منتهي"
        else:
            diagnosis = f"http_{code}: {body[:120]}"

        out["google"] = {"code": code, "diagnosis": diagnosis}
        _record(landing_page_id, "google_indexing_api", code, body)

        if code >= 400:
            _log.warning("Google Indexing %s for %s: %s", code, full_url, diagnosis)
    except Exception as exc:
        out["google"] = {"error": str(exc)[:200]}
        _record(landing_page_id, "google_indexing_api", None, str(exc))


def diagnose_google_setup() -> dict:
    """
    تشخيص جاهزية إعداد Google Indexing — يُستدعى من /admin/seo-google-check.
    يفحص: المفتاح، الحصول على token، ownership عبر محاولة dry-run.

    يرجّع dict واضح بـ ok/error_kind/next_action.
    """
    out: dict[str, Any] = {"step": "init"}

    if not GOOGLE_SA_JSON_RAW:
        out.update({
            "ok": False,
            "step": "credentials",
            "error": "GOOGLE_INDEXING_SERVICE_ACCOUNT_JSON غير معرّف في env",
            "next_action": "أضف المفتاح في Railway env vars",
        })
        return out

    try:
        sa_info = _json.loads(GOOGLE_SA_JSON_RAW)
        out["service_account_email"] = sa_info.get("client_email", "?")
        out["project_id"] = sa_info.get("project_id", "?")
    except _json.JSONDecodeError:
        out.update({
            "ok": False, "step": "parse_json",
            "error": "JSON غير صالح",
            "next_action": "تأكد من لصق المحتوى الكامل بدون قطع",
        })
        return out

    token = _get_google_access_token()
    if not token:
        out.update({
            "ok": False, "step": "oauth",
            "error": "فشل الحصول على token من Google",
            "next_action": (
                "تأكد من تثبيت google-auth + أن المفتاح غير محذوف "
                "من Google Cloud Console"
            ),
        })
        return out
    out["oauth"] = "ok"

    # dry-run: نُرسل URL وهمي ونرى الكود
    test_url = f"{SITE_URL}/_diagnostic_indexing_check"
    import requests
    try:
        r = requests.post(
            "https://indexing.googleapis.com/v3/urlNotifications:publish",
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            json={"url": test_url, "type": "URL_UPDATED"},
            timeout=10,
        )
        out["dry_run_code"] = r.status_code

        if r.status_code == 200:
            out.update({"ok": True, "step": "ready",
                        "note": "كل شيء جاهز — حذف URL التشخيصي يدوياً من Search Console"})
        elif r.status_code == 403:
            out.update({
                "ok": False, "step": "ownership",
                "error": "service account غير معتمد كـ owner",
                "next_action": (
                    "1) في Search Console اختر/أنشئ property من نوع URL prefix "
                    f"(ليس Domain) لـ {SITE_URL}\n"
                    "2) في Settings → Users and permissions → Add user\n"
                    f"3) أضف: {out.get('service_account_email')} بصلاحية Owner\n"
                    "4) أعد المحاولة"
                ),
            })
        else:
            out.update({"ok": False, "step": "http_error",
                        "error": f"HTTP {r.status_code}: {r.text[:200]}"})
    except Exception as exc:
        out.update({"ok": False, "step": "network", "error": str(exc)[:200]})

    return out


# ═══════════════════════════════════════════════════════════════════════════
#  IndexNow (Bing + Yandex + Naver + Seznam)
# ═══════════════════════════════════════════════════════════════════════════
def _submit_indexnow_direct(landing_page_id: int, full_url: str, out: dict) -> None:
    """
    يُرسل لكل محرك IndexNow مباشرة (يتجاوز الـ Next.js hook).
    البروتوكول مفتوح: نفس payload لكل المحركات.
    """
    if not INDEXNOW_KEY:
        out["indexnow"] = {"skipped": "INDEXNOW_KEY not set"}
        return

    key_location = INDEXNOW_KEY_LOCATION or f"{SITE_URL}/{INDEXNOW_KEY}.txt"
    host = SITE_URL.replace("https://", "").replace("http://", "").rstrip("/")

    payload = {
        "host":        host,
        "key":         INDEXNOW_KEY,
        "keyLocation": key_location,
        "urlList":     [full_url],
    }

    import requests
    results: dict[str, Any] = {}
    for provider, endpoint in INDEXNOW_ENGINES:
        try:
            r = requests.post(endpoint, json=payload, timeout=8,
                              headers={"Content-Type": "application/json"})
            results[provider] = {"code": r.status_code}
            _record(landing_page_id, provider, r.status_code,
                    r.text[:400] if r.text else None)
        except Exception as exc:
            results[provider] = {"error": str(exc)[:150]}
            _record(landing_page_id, provider, None, str(exc))
    out["indexnow"] = results


# ═══════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════
def submit_page(*, landing_page_id: int, slug: str) -> dict:
    """
    يخطر كل محركات البحث المتاحة بصفحة منشورة.
    يرجّع dict شامل بحالة كل خطوة.
    """
    path = _page_path(slug)
    full_url = f"{SITE_URL}{path}"
    out: dict[str, Any] = {"slug": slug, "url": full_url}

    import requests

    # 1) Next.js revalidate (لو SECRET متاح)
    secret = os.getenv("REVALIDATE_SECRET")
    if secret:
        try:
            r = requests.post(
                f"{SITE_URL}/api/revalidate",
                json={"secret": secret, "paths": [path]},
                timeout=8,
            )
            out["revalidate"] = {"code": r.status_code}
        except Exception as exc:
            out["revalidate"] = {"error": str(exc)[:200]}
    else:
        out["revalidate"] = {"skipped": "REVALIDATE_SECRET not set"}

    # 2) IndexNow متعدد المحركات (مستقل تماماً — أسرع طريق للظهور في Bing)
    _submit_indexnow_direct(landing_page_id, full_url, out)

    # 3) Google Indexing API
    _submit_to_google(landing_page_id, full_url, out)

    _log.info("index submit %s → %s", slug,
              {k: v for k, v in out.items() if k != "url"})
    return out


def resubmit_url(url: str, landing_page_id: int | None = None) -> dict:
    """
    إعادة إرسال URL محدّد (مفيد عند تحديث محتوى صفحة منشورة).
    يستخدم landing_page_id = -1 للأمور غير المرتبطة بصفحة (homepage مثلاً).
    """
    lpid = landing_page_id if landing_page_id is not None else -1
    out: dict[str, Any] = {"url": url, "resubmit": True}
    _submit_indexnow_direct(lpid, url, out)
    _submit_to_google(lpid, url, out)
    return out
