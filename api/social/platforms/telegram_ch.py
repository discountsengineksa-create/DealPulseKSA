"""Telegram public channel — يعيد استخدام نفس BOT_TOKEN.

Setup:
  1. أنشئ قناة عامة على Telegram (مثلاً @dealpulse_official).
  2. أضف البوت كـ Administrator في القناة مع صلاحية Post Messages.
  3. ضع المعرّف في env: TELEGRAM_CHANNEL_ID=@dealpulse_official
     (للقنوات الخاصة استخدم: -100xxxxxxxxxx)
"""
from __future__ import annotations

import os

import requests

from api.social.base import BaseSocialPoster, PostResult


class TelegramChannelPoster(BaseSocialPoster):
    name = "telegram"

    def is_configured(self) -> bool:
        return bool(self._token()) and bool(os.getenv("TELEGRAM_CHANNEL_ID"))

    @staticmethod
    def _token() -> str | None:
        return os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

    def post(self, text: str, image_url: str | None) -> PostResult:
        token = self._token()
        chat_id = os.getenv("TELEGRAM_CHANNEL_ID")
        if not token or not chat_id:
            return PostResult(error="BOT_TOKEN or TELEGRAM_CHANNEL_ID missing")

        base = f"https://api.telegram.org/bot{token}"

        try:
            if image_url:
                # caption في Telegram محدودة بـ 1024 حرف — نقصها لو زادت
                caption = text if len(text) <= 1024 else text[:1020] + "…"
                resp = requests.post(
                    f"{base}/sendPhoto",
                    json={
                        "chat_id": chat_id,
                        "photo": image_url,
                        "caption": caption,
                    },
                    timeout=15,
                )
            else:
                resp = requests.post(
                    f"{base}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "disable_web_page_preview": False,
                    },
                    timeout=15,
                )
        except requests.RequestException as e:
            return PostResult(error=f"network: {e}")

        if resp.status_code >= 400:
            return PostResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            data = resp.json()
            if not data.get("ok"):
                return PostResult(error=str(data.get("description", "telegram api error"))[:300])
            msg_id = data.get("result", {}).get("message_id")
            return PostResult(platform_post_id=str(msg_id) if msg_id else "")
        except Exception:
            return PostResult(platform_post_id="")
