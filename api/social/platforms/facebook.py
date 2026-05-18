"""Facebook Pages — نشر منشور مع صورة.

Setup:
  1. أنشئ Facebook Page تجارية.
  2. https://developers.facebook.com/ → أنشئ App من نوع Business.
  3. اطلب صلاحيات: pages_manage_posts, pages_read_engagement.
  4. ولّد Long-Lived Page Access Token.
  5. env:
     FB_PAGE_ID=123456789
     META_PAGE_ACCESS_TOKEN=<long-lived token>
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult

GRAPH = "https://graph.facebook.com/v21.0"


class FacebookPoster(BaseSocialPoster):
    name = "facebook"

    def is_configured(self) -> bool:
        return bool(os.getenv("FB_PAGE_ID")) and bool(os.getenv("META_PAGE_ACCESS_TOKEN"))

    def post(self, text: str, image_url: str | None) -> PostResult:
        page_id = os.getenv("FB_PAGE_ID")
        token = os.getenv("META_PAGE_ACCESS_TOKEN")
        if not page_id or not token:
            return PostResult(error="FB_PAGE_ID or META_PAGE_ACCESS_TOKEN missing")

        try:
            if image_url:
                # photo post — الصورة + الكابشن
                resp = requests.post(
                    f"{GRAPH}/{page_id}/photos",
                    data={
                        "url": image_url,
                        "caption": text,
                        "access_token": token,
                    },
                    timeout=20,
                )
            else:
                # text-only post
                resp = requests.post(
                    f"{GRAPH}/{page_id}/feed",
                    data={"message": text, "access_token": token},
                    timeout=15,
                )
        except requests.RequestException as e:
            return PostResult(error=f"network: {e}")

        if resp.status_code >= 400:
            return PostResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            post_id = data.get("post_id") or data.get("id") or ""
            return PostResult(platform_post_id=str(post_id))
        except Exception:
            return PostResult(platform_post_id="")
