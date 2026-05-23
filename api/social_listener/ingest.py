"""
Signal ingestion — نقطة الدخول لكل إشارة من المنصات.

تُستخدم من:
  • POST /api/v1/social/ingest      (أتمتة خارجية: Zapier/Make/n8n تدفع mentions)
  • مصادر مجدوَلة لاحقاً (X polling عند توفّر المفاتيح)

dedup على (platform, external_id) — نفس الإشارة لا تتكرر.
"""
from __future__ import annotations

import logging

from api.db import get_db_context
from api.social_listener.scorer import detect_lang

_log = logging.getLogger("dp.social.ingest")


def ingest_signal(
    *,
    platform: str,
    external_id: str,
    content: str,
    author_handle: str | None = None,
    author_followers: int | None = None,
    source_url: str | None = None,
) -> dict:
    """يخزّن إشارة جديدة (status='new'). يرجّع {signal_id} أو {duplicate:True}."""
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO social_signals
                    (platform, external_id, author_handle, author_followers,
                     content, lang_detected, source_url, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'new')
                ON CONFLICT (platform, external_id) DO NOTHING
                RETURNING id
                """,
                (platform, external_id, author_handle, author_followers,
                 content, detect_lang(content), source_url),
            )
            row = cur.fetchone()
    if not row:
        return {"duplicate": True}
    _log.info("social signal ingested: id=%s platform=%s", row[0], platform)
    return {"signal_id": row[0]}
