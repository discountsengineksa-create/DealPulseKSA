"""
Google Keyword Planner عبر Google Ads API (REST مباشر — بلا مكتبة google-ads الثقيلة).

يجلب **حجم البحث الشهري** + **المنافسة** للكلمات — مكمّل لـ Google Trends
(الذي يعطي شعبية نسبية فقط). يُستخدم في «محرك الفرص» لترتيب الكلمات بحجم بحثها الفعلي.

البيئة المطلوبة (تُضاف على scheduler-worker + DEALPULSEKSA):
  GOOGLE_ADS_DEVELOPER_TOKEN     — من Google Ads → API Center (موافقة قد تأخذ أياماً)
  GOOGLE_ADS_CLIENT_ID           — OAuth client (Google Cloud)
  GOOGLE_ADS_CLIENT_SECRET       — OAuth client secret
  GOOGLE_ADS_REFRESH_TOKEN       — refresh token (يُولَّد عبر OAuth playground/سكربت)
  GOOGLE_ADS_CUSTOMER_ID         — معرّف حساب Ads (10 أرقام، بلا شرطات)
  GOOGLE_ADS_LOGIN_CUSTOMER_ID   — (اختياري) لو الحساب تحت MCC
  GOOGLE_ADS_API_VERSION         — (اختياري) افتراضي v18

الجغرافيا/اللغة: السعودية = geoTargetConstants/2682، العربية = languageConstants/1019.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

_log = logging.getLogger("dp.seo.keyword_planner")

_GEO_SA = "geoTargetConstants/2682"
_LANG_AR = "languageConstants/1019"

_token_cache: dict[str, Any] = {"access_token": None, "expires_at": 0.0}


def is_configured() -> bool:
    return all(os.getenv(k) for k in (
        "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_ADS_CUSTOMER_ID"))


def _get_access_token() -> str | None:
    """يجدّد access token من refresh token (مع cache قصير)."""
    now = time.time()
    if _token_cache["access_token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["access_token"]
    try:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id":     os.getenv("GOOGLE_ADS_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_ADS_CLIENT_SECRET"),
            "refresh_token": os.getenv("GOOGLE_ADS_REFRESH_TOKEN"),
            "grant_type":    "refresh_token",
        }, timeout=20)
        j = r.json()
        tok = j.get("access_token")
        if tok:
            _token_cache["access_token"] = tok
            _token_cache["expires_at"] = now + int(j.get("expires_in", 3600))
            return tok
        _log.warning("ads token refresh failed: %s", str(j)[:200])
        return None
    except Exception as exc:  # noqa: BLE001
        _log.warning("ads token refresh error: %s", str(exc)[:200])
        return None


def fetch_keyword_volume(keywords: list[str]) -> dict[str, dict]:
    """يجلب حجم البحث الشهري + المنافسة لقائمة كلمات.
    يرجع {keyword_lower: {"avg_monthly_searches": int, "competition": str}} أو {} عند الفشل."""
    if not is_configured() or not keywords:
        return {}
    token = _get_access_token()
    if not token:
        return {}
    cid = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").replace("-", "").strip()
    ver = os.getenv("GOOGLE_ADS_API_VERSION", "v18")
    headers = {
        "Authorization": f"Bearer {token}",
        "developer-token": os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "Content-Type": "application/json",
    }
    login_cid = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace("-", "").strip()
    if login_cid:
        headers["login-customer-id"] = login_cid
    url = f"https://googleads.googleapis.com/{ver}/customers/{cid}:generateKeywordIdeas"
    body = {
        "language": _LANG_AR,
        "geoTargetConstants": [_GEO_SA],
        "keywordPlanNetwork": "GOOGLE_SEARCH",
        "keywordSeed": {"keywords": keywords[:20]},  # حد API لكل طلب
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=30)
        if r.status_code != 200:
            _log.warning("ads keyword ideas HTTP %s: %s", r.status_code, r.text[:300])
            return {}
        out: dict[str, dict] = {}
        for res in r.json().get("results", []):
            text = (res.get("text") or "").strip().lower()
            m = res.get("keywordIdeaMetrics") or {}
            if text:
                out[text] = {
                    "avg_monthly_searches": int(m.get("avgMonthlySearches") or 0),
                    "competition": m.get("competition") or "UNSPECIFIED",
                }
        return out
    except Exception as exc:  # noqa: BLE001
        _log.warning("ads keyword ideas error: %s", str(exc)[:200])
        return {}
