"""X (Twitter) — نشر تغريدة عبر API v2 مع رفع صورة عبر v1.1.

Setup:
  1. https://developer.x.com/ → Project + App.
  2. App permissions: Read + Write.
  3. ولّد OAuth 1.0a credentials (4 مفاتيح).
  4. env:
     X_API_KEY=...
     X_API_SECRET=...
     X_ACCESS_TOKEN=...
     X_ACCESS_TOKEN_SECRET=...

ملاحظة: OAuth1 يحتاج توقيع. نعتمد على requests-oauthlib لو موجود؛
       لو غير موجود، نُسجّل خطأ واضح يطلب تثبيته.
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult

UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
TWEETS_URL = "https://api.twitter.com/2/tweets"


class XTwitterPoster(BaseSocialPoster):
    name = "x"

    REQUIRED_ENV = (
        "X_API_KEY",
        "X_API_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_TOKEN_SECRET",
    )

    def is_configured(self) -> bool:
        return all(os.getenv(k) for k in self.REQUIRED_ENV)

    @staticmethod
    def _oauth1():
        try:
            from requests_oauthlib import OAuth1
        except ImportError:
            return None
        return OAuth1(
            os.getenv("X_API_KEY"),
            os.getenv("X_API_SECRET"),
            os.getenv("X_ACCESS_TOKEN"),
            os.getenv("X_ACCESS_TOKEN_SECRET"),
        )

    def post(self, text: str, image_url: str | None) -> PostResult:
        auth = self._oauth1()
        if auth is None:
            return PostResult(
                error="requests-oauthlib not installed; add it to requirements-railway.txt"
            )

        # تغريدة X محدودة بـ 280 حرف
        body_text = text if len(text) <= 280 else text[:277] + "…"

        media_ids: list[str] = []
        if image_url:
            # حمّل الصورة وارفعها لـ X
            try:
                img = requests.get(image_url, timeout=15)
                if img.status_code < 400:
                    up = requests.post(
                        UPLOAD_URL,
                        auth=auth,
                        files={"media": img.content},
                        timeout=30,
                    )
                    if up.status_code < 400:
                        media_id = up.json().get("media_id_string")
                        if media_id:
                            media_ids.append(media_id)
            except requests.RequestException:
                pass  # ننشر بدون صورة لو الرفع فشل

        payload: dict = {"text": body_text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}

        try:
            resp = requests.post(TWEETS_URL, json=payload, auth=auth, timeout=20)
        except requests.RequestException as e:
            return PostResult(error=f"network: {e}")

        if resp.status_code >= 400:
            return PostResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            tid = resp.json().get("data", {}).get("id", "")
            return PostResult(platform_post_id=str(tid))
        except Exception:
            return PostResult(platform_post_id="")
