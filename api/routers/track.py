from fastapi import APIRouter, Depends, HTTPException
from psycopg2.extras import RealDictCursor

from api.db import get_db
from api.schemas.track import (
    TrackRequest, TrackResponse,
    SearchLogRequest, SearchLogResponse,
)

router = APIRouter(prefix="/track", tags=["tracking"])


@router.post("", response_model=TrackResponse, status_code=201)
def track_action(payload: TrackRequest, conn=Depends(get_db)):
    """
    تسجيل حركة مستخدم (نقر رابط / نسخ كوبون / بحث) من أي مصدر.

    يدعم:
      - البوت (source='bot', user_id=telegram_id)
      - الموقع (source='web', user_id=web_users.id أو null للزوار)
      - الداشبورد (source='dashboard')

    يُنفَّذ في transaction واحدة:
      1. INSERT في action_logs مع source
      2. UPDATE عدادات master (للنقرات والنسخ فقط)

    هذا يُغذّي حسابات الترند الآلي مباشرةً دون تأخير.
    """
    # التحقق من وجود المتجر — يمنع تلويث السجلات ببيانات وهمية
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM master WHERE store_id = %s", (payload.store_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail=f"store '{payload.store_id}' not found")

    with conn.cursor() as cur:
        # 1. تسجيل الحدث في action_logs
        cur.execute(
            """
            INSERT INTO action_logs (user_id, store_id, action_type, details, source)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (payload.user_id, payload.store_id, payload.action, payload.details, payload.source),
        )

        # 2. تحديث العدادات في master (نقرات الرابط ونسخ الكود فقط)
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

        # 3. لمستخدمي الموقع المسجّلين: زيادة العدادات الشخصية + سجل الكود المنسوخ
        if payload.source == "web" and payload.user_id:
            if payload.action == "click_link":
                cur.execute(
                    "UPDATE web_users SET visited_clicks = visited_clicks + 1, last_seen = NOW() WHERE id = %s",
                    (payload.user_id,),
                )
            elif payload.action == "copy_coupon":
                cur.execute(
                    """
                    UPDATE web_users
                    SET store_copy_count = store_copy_count + 1,
                        copied_coupons_history = array_append(copied_coupons_history, %s),
                        last_seen = NOW()
                    WHERE id = %s
                    """,
                    (payload.store_id, payload.user_id),
                )

    return TrackResponse(
        ok=True, action=payload.action,
        store_id=payload.store_id, source=payload.source,
    )


@router.post("/search", response_model=SearchLogResponse, status_code=201)
def log_search(payload: SearchLogRequest, conn=Depends(get_db)):
    """
    تسجيل كلمة بحث في direct_search — لتحليل ما يبحث عنه المستخدمون.
    user_found=False يُحدّد فجوات المحتوى (متاجر مطلوبة لكنها غير موجودة).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO direct_search (search_keyword, store_id, user_found, platform, name_en)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (payload.keyword, payload.store_id, payload.user_found, payload.platform, payload.name_en),
        )
    return SearchLogResponse(ok=True, keyword=payload.keyword)
