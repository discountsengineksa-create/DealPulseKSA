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

import requests

from api.social.base import BaseSocialPoster, PostResult

GRAPH = "https://graph.threads.net/v1.0"

# حد Threads الصارم: 500 حرف. نُبقي header + الحقول + الرابط، ونقتطع من النبذة.
THREADS_MAX_CHARS = 500


def _truncate_for_threads(text: str, limit: int = THREADS_MAX_CHARS) -> str:
    """Threads ما يقبل أكثر من 500 حرف. لو النص أطول، نحذف فقرة النبذة كاملة
    (هي الفقرة الطويلة) ونبقي الـheader + بيانات العرض + الرابط — كافية للتحويل.
    لو ما زال طويل بعدها، نقصّ بسيط من الآخر."""
    if len(text) <= limit:
        return text
    # نحذف الفقرة التي تبدأ بـ "نبذة:" — الفقرات مفصولة بـ \n\n
    paragraphs = text.split("\n\n")
    paragraphs = [p for p in paragraphs if not p.lstrip().startswith("نبذة:")]
    stripped = "\n\n".join(paragraphs)
    if len(stripped) <= limit:
        return stripped
    # fallback نادر: لو الـheader وحده طويل (لن يحدث عملياً)
    return stripped[: limit - 1].rstrip() + "…"


class ThreadsPoster(BaseSocialPoster):
    name = "threads"

    def is_configured(self) -> bool:
        return bool(os.getenv("THREADS_USER_ID")) and bool(os.getenv("THREADS_ACCESS_TOKEN"))

    def post(self, text: str, image_url: str | None) -> PostResult:
        user_id = os.getenv("THREADS_USER_ID")
        token = os.getenv("THREADS_ACCESS_TOKEN")
        if not user_id or not token:
            return PostResult(error="THREADS_USER_ID or THREADS_ACCESS_TOKEN missing")

        # تطبيق حد الـ500 حرف الصارم لـThreads
        text = _truncate_for_threads(text)

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

        # Step 2: publish
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
