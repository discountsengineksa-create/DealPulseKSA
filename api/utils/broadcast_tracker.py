"""
أدوات حقن وإعادة كتابة الـtracking في رسائل الحملات.

الفكرة:
  1. نولّد tracking_token UUID فريد لكل مستلم.
  2. نُسجّل كل URL أصلي في الحملة كصف في broadcast_link_targets (مرة لكل URL).
  3. نُعيد كتابة الـURLs في الرسالة لتمر عبر endpoint إعادة التوجيه
     (يحدّث click_count + يسجّل في broadcast_link_clicks ثم 302 للأصل).
  4. للبريد فقط: نحقن صورة 1×1 شفافة في النهاية تطلب pixel من endpoint
     يحدّث open_count + يسجّل في broadcast_email_opens.

التهيئة:
  ضع في .env:
    TRACKING_BASE_URL=https://your-api.dealpulseksa.com
  (يجب أن يكون متاحاً من الإنترنت — Railway URL أو دومين خاص)
  لو غائب → نخطّي tracking بهدوء (نسجّل تحذير) دون كسر الإرسال.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from typing import Iterable

_log = logging.getLogger("dp.broadcast_tracker")

# Regex لاستخراج URLs من نص أو HTML (يلتقط href="..." وأيضاً URLs العارية)
_URL_HREF_RE = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
_URL_BARE_RE = re.compile(
    r'(?<![">\'])(https?://[^\s<>"\']+)',  # تجنّب href المُلتقطة سابقاً
    re.IGNORECASE,
)


def tracking_base_url() -> str | None:
    """يرجّع TRACKING_BASE_URL من البيئة أو None."""
    base = os.getenv("TRACKING_BASE_URL", "").strip().rstrip("/")
    return base or None


def is_tracking_enabled() -> bool:
    return tracking_base_url() is not None


def generate_token() -> str:
    """UUID4 بدون شرطات (32 حرف، URL-safe)."""
    return uuid.uuid4().hex


# ════════════════════════════════════════════════════════════════════════════
# تسجيل URLs الحملة → broadcast_link_targets
# ════════════════════════════════════════════════════════════════════════════

def extract_urls(body: str) -> list[str]:
    """يستخرج كل الـURLs الفريدة من نص/HTML."""
    if not body:
        return []
    urls: set[str] = set()
    # href="..." في HTML
    for m in _URL_HREF_RE.finditer(body):
        u = m.group(1).strip()
        if u.startswith(("http://", "https://")):
            urls.add(u)
    # URLs عارية في نص خام أو caption
    for m in _URL_BARE_RE.finditer(body):
        u = m.group(1).strip().rstrip(".,;:")
        if u and u.startswith(("http://", "https://")):
            urls.add(u)
    return list(urls)


def register_links(conn, *, broadcast_id: int, broadcast_kind: str,
                   urls: Iterable[str]) -> dict[str, int]:
    """يُسجّل كل URL في broadcast_link_targets. يرجّع {url: link_target_id}."""
    out: dict[str, int] = {}
    if not urls:
        return out
    with conn.cursor() as cur:
        for url in set(urls):
            cur.execute(
                "INSERT INTO broadcast_link_targets "
                "(broadcast_id, broadcast_kind, original_url) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (broadcast_id, broadcast_kind, original_url) "
                "DO UPDATE SET original_url = EXCLUDED.original_url "  # ترجيع الـrow
                "RETURNING id",
                (broadcast_id, broadcast_kind, url),
            )
            out[url] = cur.fetchone()[0]
        conn.commit()
    return out


# ════════════════════════════════════════════════════════════════════════════
# إعادة كتابة الجسم للمستلم
# ════════════════════════════════════════════════════════════════════════════

def rewrite_body_for_recipient(
    body: str, *,
    tracking_token: str,
    url_to_id: dict[str, int],
    is_html: bool = True,
) -> str:
    """يستبدل كل URL أصلي بـ tracking URL خاص بهذا المستلم.

    is_html=True → نستبدل في href="..." (يحافظ على شكل الـHTML)
    is_html=False → نستبدل URLs عارية (للتليجرام / النص الخام)
    """
    base = tracking_base_url()
    if not base or not body or not url_to_id:
        return body

    def _tracked(original_url: str) -> str:
        lid = url_to_id.get(original_url)
        if lid is None:
            return original_url
        return f"{base}/bt/c/{tracking_token}/{lid}"

    if is_html:
        def _replace_href(match: re.Match) -> str:
            orig = match.group(1).strip()
            if orig.startswith(("http://", "https://")) and orig in url_to_id:
                return f'href="{_tracked(orig)}"'
            return match.group(0)
        body = _URL_HREF_RE.sub(_replace_href, body)
        # نستبدل أيضاً الـURLs العارية في النص داخل HTML (مثل في <p>)
        def _replace_bare(match: re.Match) -> str:
            orig = match.group(1).strip().rstrip(".,;:")
            if orig in url_to_id:
                return _tracked(orig)
            return match.group(0)
        body = _URL_BARE_RE.sub(_replace_bare, body)
    else:
        def _replace_bare2(match: re.Match) -> str:
            orig = match.group(1).strip().rstrip(".,;:")
            if orig in url_to_id:
                return _tracked(orig)
            return match.group(0)
        body = _URL_BARE_RE.sub(_replace_bare2, body)

    return body


def inject_open_pixel(html_body: str, tracking_token: str) -> str:
    """يحقن tracking pixel 1×1 قبل </body> (أو في النهاية لو ما فيه)."""
    base = tracking_base_url()
    if not base or not html_body:
        return html_body
    pixel = (
        f'<img src="{base}/bt/o/{tracking_token}.gif" '
        f'width="1" height="1" alt="" '
        f'style="display:block;width:1px;height:1px;border:0;" />'
    )
    # نحقن قبل </body> لو موجود
    if "</body>" in html_body.lower():
        # حساس لحالة الأحرف
        idx = html_body.lower().rfind("</body>")
        return html_body[:idx] + pixel + html_body[idx:]
    return html_body + pixel
