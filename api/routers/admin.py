"""
Admin endpoints — يستدعيها الـ dashboard فقط.

POST /api/v1/admin/broadcast/{master_id}
    يطلق نشر العرض على كل منصات السوشيال في الخلفية (FastAPI BackgroundTasks).
    الـ Header `X-Admin-Secret` لازم يطابق ADMIN_SHARED_SECRET.
"""
from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from api.social.dispatcher import broadcast_to_all_platforms

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/broadcast/{master_id}")
def broadcast(
    master_id: int,
    background_tasks: BackgroundTasks,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    expected = os.getenv("ADMIN_SHARED_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_SHARED_SECRET not configured")
    if x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="forbidden")

    background_tasks.add_task(broadcast_to_all_platforms, master_id)
    return {"status": "queued", "master_id": master_id}
