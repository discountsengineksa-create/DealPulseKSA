"""واجهة موحّدة لجميع منشورات منصّات السوشيال."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PostResult:
    platform_post_id: str | None = None
    error: str | None = None


class NotConfiguredError(Exception):
    """يُرفع عندما تكون متغيرات البيئة للمنصة ناقصة — يُسجَّل status='skipped'."""


class BaseSocialPoster:
    """
    كل منصة جديدة ترث من هذا الكلاس وتُعرّف:
      - name: اسم المنصة (ضع نفس اسم العمود platform في social_posts_log)
      - is_configured() -> bool
      - post(text, image_url) -> PostResult
    """

    name: str = "base"

    def is_configured(self) -> bool:
        raise NotImplementedError

    def post(self, text: str, image_url: str | None) -> PostResult:
        raise NotImplementedError
