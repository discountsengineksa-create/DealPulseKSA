"""Threads (Meta) — Graph API منفصل بأسلوب مشابه لـ Instagram.

Setup:
  1. https://developers.facebook.com/docs/threads
  2. أنشئ Threads App → اربطه بحساب Threads الخاص بالعلامة.
  3. صلاحيات: threads_basic, threads_content_publish.
  4. env:
     THREADS_USER_ID=1234567890
     THREADS_ACCESS_TOKEN=<long-lived user token>
"""
from __future__ import annotations

import os
import time

import requests

from api.social.base import BaseSocialPoster, PostResult

GRAPH = "https://graph.threads.net/v1.0"

_POLL_INTERVAL_SEC = 3
_POLL_MAX_ATTEMPTS = 12  # ~36s — Threads يتطلّب انتظار معالجة الـ container قبل النشر (مثل انستقرام)


class ThreadsPoster(BaseSocialPoster):
    name = "threads"

    def is_configured(self) -> bool:
        return bool(os.getenv("THREADS_USER_ID")) and bool(os.getenv("THREADS_ACCESS_TOKEN"))

    def post(self, text: str, image_url: str | None) -> PostResult:
        user_id = os.getenv("THREADS_USER_ID")
        token = os.getenv("THREADS_ACCESS_TOKEN")
        if not user_id or not token:
            return PostResult(error="THREADS_USER_ID or THREADS_ACCESS_TOKEN missing")

        # Step 1: container
        params = {
            "media_type": "IMAGE" if image_url else "TEXT",
            "text": text,
            "access_token": token,
        }
        if image_url:
            params["image_url"] = image_url

        try:
            create = requests.post(
                f"{GRAPH}/{user_id}/threads",
                data=params,
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
            return PostResult(error="no creation_id")

        # Step 2: انتظر معالجة الـ container — Threads يرفض النشر الفوري (خصوصاً للصور)
        last_status = None
        for _ in range(_POLL_MAX_ATTEMPTS):
            time.sleep(_POLL_INTERVAL_SEC)
            try:
                check = requests.get(
                    f"{GRAPH}/{creation_id}",
                    params={"fields": "status", "access_token": token},
                    timeout=10,
                )
            except requests.RequestException:
                continue
            if check.status_code >= 400:
                continue
            try:
                last_status = check.json().get("status")
            except Exception:
                continue
            if last_status == "FINISHED":
                break
            if last_status in ("ERROR", "EXPIRED"):
                return PostResult(error=f"container {last_status}")

        if last_status != "FINISHED":
            return PostResult(
                error=f"container not ready after {_POLL_MAX_ATTEMPTS * _POLL_INTERVAL_SEC}s (last={last_status})"
            )

        # Step 3: publish
        try:
            publish = requests.post(
                f"{GRAPH}/{user_id}/threads_publish",
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
