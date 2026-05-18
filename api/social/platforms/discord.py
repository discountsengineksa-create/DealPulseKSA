"""Discord — أبسط منصة، webhook واحد بدون OAuth.

Setup:
  1. في سيرفر Discord: Server Settings → Integrations → Webhooks → New Webhook.
  2. انسخ Webhook URL وضعه في env: DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult


class DiscordPoster(BaseSocialPoster):
    name = "discord"

    def is_configured(self) -> bool:
        return bool(os.getenv("DISCORD_WEBHOOK_URL"))

    def post(self, text: str, image_url: str | None) -> PostResult:
        url = os.getenv("DISCORD_WEBHOOK_URL")
        if not url:
            return PostResult(error="DISCORD_WEBHOOK_URL missing")

        payload: dict = {"content": text}
        if image_url:
            # تضمين الصورة كـ embed thumbnail يحافظ على نظافة العرض
            payload["embeds"] = [{"image": {"url": image_url}}]

        try:
            # ?wait=true يجعل Discord يرجّع id الرسالة
            resp = requests.post(
                f"{url}?wait=true",
                json=payload,
                timeout=10,
            )
        except requests.RequestException as e:
            return PostResult(error=f"network: {e}")

        if resp.status_code >= 400:
            return PostResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            return PostResult(platform_post_id=str(data.get("id") or ""))
        except Exception:
            return PostResult(platform_post_id="")
