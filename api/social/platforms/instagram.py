"""Instagram Business — نشر صورة + caption عبر Graph API.

Setup:
  1. Instagram Business account متّصل بـ Facebook Page (نفس Page المستخدمة لـ FB).
  2. صلاحيات الـ App: instagram_basic, instagram_content_publish, pages_show_list.
  3. env:
     IG_BUSINESS_ID=17841401234567890
     META_PAGE_ACCESS_TOKEN=<نفس التوكن الطويل المستخدم في Facebook>

ملاحظة: Instagram يتطلّب صورة (لا يقبل نص-فقط). image_url لازم يكون public HTTPS.

Flow: create container -> poll حتى FINISHED -> publish (يلزم polling لأن الـ
container processing async — لو نشرنا فوراً يطلع Media ID is not available).
"""
from __future__ import annotations

import os
import time

import requests

from api.social.base import BaseSocialPoster, PostResult

GRAPH = "https://graph.facebook.com/v21.0"

_POLL_INTERVAL_SEC = 2
_POLL_MAX_ATTEMPTS = 15  # 30 ثانية إجمالاً — كافية لصور صغيرة


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

        # Step 2: poll حالة الـ container حتى FINISHED
        last_status = None
        for _ in range(_POLL_MAX_ATTEMPTS):
            time.sleep(_POLL_INTERVAL_SEC)
            try:
                check = requests.get(
                    f"{GRAPH}/{creation_id}",
                    params={"fields": "status_code,status", "access_token": token},
                    timeout=10,
                )
            except requests.RequestException:
                continue
            if check.status_code >= 400:
                continue
            try:
                last_status = check.json().get("status_code")
            except Exception:
                continue
            if last_status == "FINISHED":
                break
            if last_status in ("ERROR", "EXPIRED"):
                detail = check.json().get("status", "")
                return PostResult(error=f"container {last_status}: {detail[:200]}")

        if last_status != "FINISHED":
            return PostResult(
                error=f"container not ready after {_POLL_MAX_ATTEMPTS * _POLL_INTERVAL_SEC}s (last={last_status})"
            )

        # Step 3: انشر الـ container
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
