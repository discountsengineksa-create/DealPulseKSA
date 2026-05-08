from fastapi import APIRouter, Depends, HTTPException

from api.db import get_db
from api.schemas.track import TrackRequest, TrackResponse

router = APIRouter(prefix="/track", tags=["tracking"])


@router.post("", response_model=TrackResponse, status_code=201)
def track_action(payload: TrackRequest, conn=Depends(get_db)):
    """
    تسجيل حركة مستخدم (نقر رابط / نسخ كوبون / بحث).

    يُنفَّذ في transaction واحدة:
      1. INSERT في action_logs
      2. UPDATE عدادات master (total_coupon_copies / total_link_clicks)

    هذا يُغذّي حسابات الترند الآلي مباشرةً دون تأخير.
    """
    # التحقق من وجود المتجر قبل التسجيل — يمنع تلويث السجلات ببيانات وهمية
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

    with conn.cursor() as cur:
        # 1. تسجيل الحدث في السجل التفصيلي
        cur.execute(
            """
            INSERT INTO action_logs (user_id, store_id, action_type, details)
            VALUES (%s, %s, %s, %s)
            """,
            (payload.user_id, payload.store_id, payload.action, payload.details),
        )

        # 2. تحديث العدادات في الماستر (استعلام واحد بدلاً من read-then-write)
        cur.execute(
            """
            UPDATE master SET
                total_coupon_copies = total_coupon_copies
                    + CASE WHEN %s = 'copy_coupon' THEN 1 ELSE 0 END,
                total_link_clicks   = total_link_clicks
                    + CASE WHEN %s = 'click_link'  THEN 1 ELSE 0 END
            WHERE store_id = %s
            """,
            (payload.action, payload.action, payload.store_id),
        )

    return TrackResponse(ok=True, action=payload.action, store_id=payload.store_id)
