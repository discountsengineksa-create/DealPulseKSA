"""
Generic ops-alert sender. Reuses the Resend → SMTP fallback already proven
in production for password resets (extracted into `_send_email` in
api/auth_utils.py).
"""
from __future__ import annotations

import logging
import os
from typing import Literal, Optional

from api.auth_utils import _send_email

_log = logging.getLogger("dp.alerts")

OPS_EMAIL = os.getenv("OPS_ALERT_EMAIL", "dealpulesksa@gmail.com")

Severity = Literal["info", "warning", "critical"]

_BADGE: dict[str, tuple[str, str]] = {
    "info":     ("🟢", "#10B981"),
    "warning":  ("🟡", "#F59E0B"),
    "critical": ("🔴", "#DC2626"),
}


def send_ops_alert(
    *,
    subject: str,
    body_html: str,
    severity: Severity = "info",
    to: Optional[str] = None,
) -> bool:
    """
    Send a stylised ops alert. The HTML shell adds a severity badge and
    a side-bar in the appropriate colour. `body_html` should be valid HTML
    fragments (paragraphs, lists, code blocks).
    """
    icon, color = _BADGE[severity]
    final_subject = f"{icon} [DealPulse] {subject}"
    html = f"""<!doctype html>
<html lang="ar" dir="rtl">
<head><meta charset="utf-8"><title>{subject}</title></head>
<body style="font-family: Cairo, Arial, sans-serif; background:#FAFAF8; padding:20px;">
  <div style="max-width:640px; margin:0 auto; background:#fff; border:1px solid #E5E7EB;
              border-right:6px solid {color}; border-radius:12px; padding:24px;">
    <h2 style="margin:0 0 12px 0; color:#111827;">{icon} {subject}</h2>
    <div style="color:#374151; line-height:1.7;">{body_html}</div>
    <hr style="border:none; border-top:1px solid #E5E7EB; margin:20px 0;">
    <p style="color:#6B7280; font-size:12px; margin:0;">
      DealPulse KSA · automated ops alert · severity = <b>{severity}</b>
    </p>
  </div>
</body>
</html>"""
    target = to or OPS_EMAIL
    _log.info("Dispatching ops alert (%s) to %s — %s", severity, target, subject)
    return _send_email(to=target, subject=final_subject, html=html)
