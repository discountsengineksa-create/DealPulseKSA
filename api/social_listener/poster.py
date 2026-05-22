"""
Response poster — ينشر الرد على المنصة أو يعلّمه جاهزاً للاعتماد اليدوي.

استراتيجية النشر (بلا مفاتيح OAuth معقّدة):
  • لو SOCIAL_POST_WEBHOOK مضبوط → نرسل الرد + السياق له (يربطه المستخدم
    بـ Zapier/Make ليُنشر فعلياً على المنصة). هذا أبسط وأأمن من تخزين توكنات
    write لكل منصة، ويجعل النظام «بلا تيرمنال» بالكامل.
  • غير ذلك → نعلّم الرد review_status='approved' (جاهز، ينسخه المشغّل).
"""
from __future__ import annotations

import logging
import os

from psycopg2.extras import RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.social.poster")


def post_response(response_id: int) -> dict:
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT r.id, r.rendered_text, r.link_url, r.review_status,
                       s.platform, s.external_id, s.source_url, s.author_handle
                FROM social_responses r
                JOIN social_signals s ON s.id = r.signal_id
                WHERE r.id = %s
                """,
                (response_id,),
            )
            r = cur.fetchone()
            if not r:
                return {"ok": False, "error": "not_found"}
            if r["review_status"] == "posted":
                return {"ok": True, "already_posted": True}

            webhook = os.getenv("SOCIAL_POST_WEBHOOK")
            if not webhook:
                cur.execute(
                    "UPDATE social_responses SET review_status='approved' WHERE id=%s",
                    (response_id,),
                )
                return {"ok": True, "via": "manual",
                        "note": "اعتُمد — اربط SOCIAL_POST_WEBHOOK للنشر التلقائي"}

            import requests
            try:
                resp = requests.post(
                    webhook,
                    json={
                        "text": r["rendered_text"],
                        "link": r["link_url"],
                        "platform": r["platform"],
                        "external_id": r["external_id"],
                        "reply_to": r["author_handle"],
                        "source_url": r["source_url"],
                    },
                    timeout=8,
                )
                ok = resp.status_code < 400
                cur.execute(
                    "UPDATE social_responses SET review_status=%s, posted_at=NOW(), error_message=%s WHERE id=%s",
                    ("posted" if ok else "failed",
                     None if ok else f"webhook HTTP {resp.status_code}", response_id),
                )
                return {"ok": ok, "via": "webhook", "code": resp.status_code}
            except Exception as exc:
                cur.execute(
                    "UPDATE social_responses SET review_status='failed', error_message=%s WHERE id=%s",
                    (str(exc)[:500], response_id),
                )
                return {"ok": False, "error": str(exc)[:200]}
