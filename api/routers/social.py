"""
Social ingestion endpoint — تستقبل الإشارات (mentions) من الأتمتة الخارجية.

POST /api/v1/social/ingest  (X-Admin-Secret)
    تدفع منصّات/أدوات (Zapier/Make/n8n) إشارة جديدة، فنخزّنها، نحسب النية،
    نطابق متجراً، ونرجّع الرد المُجهّز فوراً ليُنشر آلياً.
"""
from __future__ import annotations

import os
import secrets as _secrets

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from api.utils.rate_limit import LIMIT_SOCIAL_INGEST, limiter

router = APIRouter(prefix="/social", tags=["social"])


def _verify(secret: str) -> None:
    expected = os.getenv("ADMIN_SHARED_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_SHARED_SECRET not configured")
    # compare_digest يحمي من timing attacks
    if not _secrets.compare_digest(secret or "", expected):
        raise HTTPException(status_code=403, detail="forbidden")


class IngestRequest(BaseModel):
    platform: str
    external_id: str
    content: str
    author_handle: str | None = None
    author_followers: int | None = None
    source_url: str | None = None


@router.post("/ingest")
@limiter.limit(LIMIT_SOCIAL_INGEST)
def ingest(payload: IngestRequest, request: Request, x_admin_secret: str = Header(..., alias="X-Admin-Secret")):
    _verify(x_admin_secret)
    from api.social_listener.ingest import ingest_signal
    from api.social_listener.responder import process_new_signals

    res = ingest_signal(
        platform=payload.platform,
        external_id=payload.external_id,
        content=payload.content,
        author_handle=payload.author_handle,
        author_followers=payload.author_followers,
        source_url=payload.source_url,
    )
    if res.get("duplicate"):
        return {"status": "duplicate"}

    # عالج فوراً حتى ترجع الأتمتة بالرد الجاهز
    process_new_signals(batch=5)

    from psycopg2.extras import RealDictCursor
    from api.db import get_db_context
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, rendered_text, link_url, review_status, master_id "
                "FROM social_responses WHERE signal_id=%s ORDER BY id DESC LIMIT 1",
                (res["signal_id"],),
            )
            resp = cur.fetchone()
    return {"status": "ingested", "signal_id": res["signal_id"],
            "response": dict(resp) if resp else None}
