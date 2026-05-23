"""Pinterest — إنشاء Pin جديد عبر API v5.

Setup:
  1. https://developers.pinterest.com/ → سجّل App.
  2. OAuth scope: pins:write, boards:read.
  3. أنشئ Board لـ DealPulse، انسخ board_id.
  4. env:
     PINTEREST_ACCESS_TOKEN=<bearer token>
     PINTEREST_BOARD_ID=<board id>
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult


class PinterestPoster(BaseSocialPoster):
    name = "pinterest"

    def is_configured(self) -> bool:
        return bool(os.getenv("PINTEREST_ACCESS_TOKEN")) and bool(
            os.getenv("PINTEREST_BOARD_ID")
        )

    def post(self, text: str, image_url: str | None) -> PostResult:
        token = os.getenv("PINTEREST_ACCESS_TOKEN")
        board_id = os.getenv("PINTEREST_BOARD_ID")
        if not token or not board_id:
            return PostResult(error="PINTEREST_* env missing")
        if not image_url:
            return PostResult(error="Pinterest requires an image")

        # Pinterest title محدود بـ 100 حرف — نأخذ السطر الأول كعنوان والباقي وصف
        first_line, _, rest = text.partition("\n")
        title = first_line[:100] or "DealPulse"
        body = (rest or text)[:500]

        payload = {
            "board_id": board_id,
            "title": title,
            "description": body,
            "media_source": {
                "source_type": "image_url",
                "url": image_url,
            },
        }

        try:
            resp = requests.post(
                "https://api.pinterest.com/v5/pins",
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network: {e}")

        if resp.status_code >= 400:
            return PostResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            pid = resp.json().get("id", "")
            return PostResult(platform_post_id=str(pid))
        except Exception:
            return PostResult(platform_post_id="")
