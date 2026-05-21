"""
Admin endpoints — يستدعيها الـ dashboard فقط.

POST /api/v1/admin/broadcast/{master_id}
    يطلق نشر العرض على كل منصات السوشيال في الخلفية (FastAPI BackgroundTasks).
    الـ Header `X-Admin-Secret` لازم يطابق ADMIN_SHARED_SECRET.

POST /api/v1/admin/trigger-directive
    يولّد توجيه AI فوراً (يدوي — عادة الـ scheduler يشغله كل 3 ساعات).
"""
from __future__ import annotations

import os

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from api.social.dispatcher import broadcast_to_all_platforms

router = APIRouter(prefix="/admin", tags=["admin"])


def _verify_admin(x_admin_secret: str) -> None:
    expected = os.getenv("ADMIN_SHARED_SECRET")
    if not expected:
        raise HTTPException(status_code=503, detail="ADMIN_SHARED_SECRET not configured")
    if x_admin_secret != expected:
        raise HTTPException(status_code=403, detail="forbidden")


@router.post("/broadcast/{master_id}")
def broadcast(
    master_id: int,
    background_tasks: BackgroundTasks,
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    _verify_admin(x_admin_secret)
    background_tasks.add_task(broadcast_to_all_platforms, master_id)
    return {"status": "queued", "master_id": master_id}


@router.post("/trigger-directive")
def trigger_directive(
    x_admin_secret: str = Header(..., alias="X-Admin-Secret"),
):
    """
    Manual trigger للـ LLM directive generator. يُستخدم للاختبار وللحالات
    الطارئة بدون انتظار الـ scheduler. النتيجة تعود مباشرة في الـ response
    (مش background) عشان نقدر نشوف cache_hit + cost + summary.
    """
    _verify_admin(x_admin_secret)
    # Lazy import — avoid loading the LLM SDK on every admin request
    from api.utils.llm_service import generate_directive
    result = generate_directive()
    return {
        "directive_id":         result.get("directive_id"),
        "cache_hit":            result.get("cache_hit"),
        "summary":              result.get("summary"),
        "directives_count":     len(result.get("directives") or []),
        "model":                result.get("model"),
        "provider":             result.get("provider"),
        "fallback_used":        result.get("fallback_used"),
        "cost_usd":             result.get("cost_usd"),
        "tokens_input":         result.get("tokens_input"),
        "tokens_output":        result.get("tokens_output"),
        "refused_by_guardian":  result.get("refused_by_guardian"),
        "refused_reason":       result.get("refused_reason"),
    }
