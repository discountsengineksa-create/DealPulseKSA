"""LinkedIn — نشر باستخدام UGC Posts API.

Setup:
  1. https://www.linkedin.com/developers/ → أنشئ App.
  2. اطلب OAuth scopes: w_member_social.
  3. ولّد access token (تنتهي بعد 60 يوم — يحتاج refresh دوري).
  4. احصل على authorURN (مثلاً urn:li:person:abc123 من /v2/userinfo).
  5. env:
     LINKEDIN_ACCESS_TOKEN=<bearer>
     LINKEDIN_AUTHOR_URN=urn:li:person:abc123    # أو urn:li:organization:123

ملاحظة: لرفع الصورة لازم 3 خطوات (register → upload → reference) — هنا نبدأ بنشر نصي
       موثوق أولاً ونترك دعم الصورة لتحسين لاحق (TODO).
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult


class LinkedInPoster(BaseSocialPoster):
    name = "linkedin"

    def is_configured(self) -> bool:
        return bool(os.getenv("LINKEDIN_ACCESS_TOKEN")) and bool(
            os.getenv("LINKEDIN_AUTHOR_URN")
        )

    def post(self, text: str, image_url: str | None) -> PostResult:
        token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        author = os.getenv("LINKEDIN_AUTHOR_URN")
        if not token or not author:
            return PostResult(error="LINKEDIN_* env missing")

        # نص فقط — رفع الصورة يحتاج 3 طلبات إضافية، نضيفها لاحقاً.
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        try:
            resp = requests.post(
                "https://api.linkedin.com/v2/ugcPosts",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json",
                },
                timeout=20,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network: {e}")

        if resp.status_code >= 400:
            return PostResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}")

        # LinkedIn يرجّع id في header
        post_id = resp.headers.get("x-restli-id") or ""
        return PostResult(platform_post_id=post_id)
