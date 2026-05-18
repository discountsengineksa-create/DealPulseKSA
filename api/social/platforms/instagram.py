"""Instagram Business — نشر صورة + caption عبر Graph API.

Setup:
  1. Instagram Business account متّصل بـ Facebook Page (نفس Page المستخدمة لـ FB).
  2. صلاحيات الـ App: instagram_basic, instagram_content_publish, pages_show_list.
  3. env:
     IG_BUSINESS_ID=17841401234567890
     META_PAGE_ACCESS_TOKEN=<نفس التوكن الطويل المستخدم في Facebook>

ملاحظة: Instagram يتطلّب صورة (لا يقبل نص-فقط). image_url لازم يكون public HTTPS.
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult

GRAPH = "https://graph.facebook.com/v21.0"


class InstagramPoster(BaseSocialPoster):
    name = "instagram"

    def is_configured(self) -> bool:
        return bool(os.getenv("IG_BUSINESS_ID")) and bool(os.getenv("META_PAGE_ACCESS_TOKEN"))

    def post(self, text: str, image_url: str | None) -> PostResult:
        ig_id = os.getenv("IG_BUSINESS_ID")
        token = os.getenv("META_PAGE_ACCESS_TOKEN")
        if not ig_id or not token:
            return PostResult(error="IG_BUSINESS_ID or META_PAGE_ACCESS_TOKEN missing")
        if not image_url:
            return PostResult(error="Instagram requires an image (logo_url empty)")

        # Step 1: أنشئ container
        try:
            create = requests.post(
                f"{GRAPH}/{ig_id}/media",
                data={
                    "image_url": image_url,
                    "caption": text,
                    "access_token": token,
                },
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network (create): {e}")
        if create.status_code >= 400:
            return PostResult(error=f"create HTTP {create.status_code}: {create.text[:300]}")

        try:
            creation_id = create.json().get("id")
        except Exception:
            return PostResult(error="invalid create response")
        if not creation_id:
            return PostResult(error="no creation_id returned")

        # Step 2: انشر الـ container
        try:
            publish = requests.post(
                f"{GRAPH}/{ig_id}/media_publish",
                data={"creation_id": creation_id, "access_token": token},
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network (publish): {e}")
        if publish.status_code >= 400:
            return PostResult(error=f"publish HTTP {publish.status_code}: {publish.text[:300]}")

        try:
            pid = publish.json().get("id", "")
            return PostResult(platform_post_id=str(pid))
        except Exception:
            return PostResult(platform_post_id="")
