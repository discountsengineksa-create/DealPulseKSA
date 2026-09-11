"""
تذكيرات مواسم التخفيضات — التقاط الزائر الذي جاء يخطّط لا يشتري.

POST /api/v1/reminders/subscribe   → اشتراك بإيميل واحد (بلا تسجيل)
GET  /api/v1/reminders/unsubscribe → إلغاء عبر التوكن الموقّع في كل رسالة

## لماذا إيميل واحد بلا حساب

صفحة `/calendar` تجيب على سؤال إجابته تُنهي الجلسة: «متى يبدأ الموسم؟» — يأخذ
الزائر التاريخ وتنتهي حاجته. المشكلة ليست ضعف الروابط بل أن نيّته **تخطيط**:
الموسم بعد أسابيع فلا شيء يفعله اليوم مهما عرضنا عليه.

فالهدف ليس أن يتصفّح أكثر، بل أن نعاود الاتصال به يوم يصير جاهزاً فعلاً. وصفحة
التسجيل عندنا خمسة حقول (جوال، جنس، إيميل، كلمة مرور، موافقة) — بوابة كهذه على
زائر بلا نيّة شراء تقتل حجم الالتقاط، وحجم الالتقاط هو الهدف كله هنا. التسجيل
يأتي لاحقاً من داخل رسالة التذكير، حين يكون قد عرفنا وأثبت اهتمامه.

## المواسم

مصدرها `app/calendar/data.ts` في ريبو الويب (12 موسماً بمعرّفات ثابتة) لا جدول
`seasonal_events` — لذلك `season_id` نصّ يتحقّق منه مقابل قائمة بيضاء هنا، بدل
مفتاح أجنبي يكسر عند أول اختلاف بين المصدرين.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..db import get_db

router = APIRouter(prefix="/reminders", tags=["reminders"])

# معرّفات المواسم في app/calendar/data.ts — قائمة بيضاء تمنع تلويث الجدول
# بقيم عشوائية من عميل مزوّر. أي موسم جديد يُضاف هنا وهناك معاً.
VALID_SEASONS: frozenset[str] = frozenset({
    "winter-clearance", "founding-day", "ramadan", "eid-fitr", "eid-adha",
    "summer-sale", "back-to-school", "national-day", "riyadh-season",
    "eleven-eleven", "white-friday", "twelve-twelve",
})

# تحقّق عملي لا صارم: يرفض الأخطاء الواضحة بلا رفض عناوين صحيحة غريبة الشكل.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

SITE_URL = os.getenv("SITE_URL", "https://www.dealpulseksa.com").rstrip("/")


class SubscribeIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    season_id: str = Field(min_length=2, max_length=64)
    season_name: str | None = Field(default=None, max_length=120)
    # السنة الميلادية التي يعود فيها الموسم — تحسبها الواجهة من seasonStatus()
    season_year: int = Field(ge=2020, le=2100)
    source: str = Field(default="calendar", max_length=32)
    visitor_id: str | None = Field(default=None, max_length=64)
    lang: str = Field(default="ar", max_length=8)


class SubscribeOut(BaseModel):
    ok: bool
    already: bool = False
    message: str


@router.post("/subscribe", response_model=SubscribeOut)
def subscribe(payload: SubscribeIn, request: Request, conn=Depends(get_db)):
    email = payload.email.strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="البريد الإلكتروني غير صالح")

    season_id = payload.season_id.strip()
    if season_id not in VALID_SEASONS:
        raise HTTPException(status_code=422, detail="موسم غير معروف")

    # ON CONFLICT: إعادة الاشتراك في نفس الموسم والسنة تُحدِّث ولا تُكرِّر، وتُعيد
    # تفعيل من ألغى سابقاً ثم عاد — سلوك متوقّع أكثر من رفض صامت.
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO season_reminders
                   (email, season_id, season_name, season_year,
                    source, visitor_id, lang)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lower(email), season_id, season_year) DO UPDATE
               SET status      = 'active',
                   season_name = COALESCE(EXCLUDED.season_name, season_reminders.season_name),
                   updated_at  = NOW()
            RETURNING (xmax <> 0) AS was_update
            """,
            (email, season_id, payload.season_name, payload.season_year,
             payload.source, payload.visitor_id, payload.lang),
        )
        row = cur.fetchone()
        conn.commit()

    already = bool(row[0]) if row else False
    return SubscribeOut(
        ok=True,
        already=already,
        message="تم — بنذكّرك قبل الموسم." if not already else "أنت مشترك في هذا الموسم أصلاً.",
    )


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe(token: str = Query(min_length=8, max_length=64), conn=Depends(get_db)):
    """
    إلغاء بضغطة واحدة من داخل الرسالة — بلا تسجيل دخول ولا تأكيد.

    يُرجع HTML لا JSON لأن الرابط يُفتح في متصفّح المستخدم مباشرةً من بريده.
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE season_reminders SET status='unsubscribed', updated_at=NOW() "
            "WHERE unsubscribe_token::text = %s RETURNING season_name",
            (token,),
        )
        row = cur.fetchone()
        conn.commit()

    ok = row is not None
    title = "تم إلغاء الاشتراك" if ok else "الرابط غير صالح"
    body = (
        "ما راح توصلك تذكيرات هذا الموسم بعد الآن."
        if ok else
        "الرابط منتهي أو غير صحيح."
    )
    return HTMLResponse(
        f"""<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>{title}</title>
<style>body{{font-family:system-ui,-apple-system,'Segoe UI',sans-serif;background:#f8fafc;
margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}}
.c{{background:#fff;border:1px solid #e2e8f0;border-radius:16px;padding:32px;max-width:420px;
text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.06)}}
h1{{font-size:20px;margin:0 0 8px;color:#0f172a}}p{{color:#475569;font-size:14px;line-height:1.7;margin:0 0 20px}}
a{{display:inline-block;background:#059669;color:#fff;text-decoration:none;padding:10px 20px;
border-radius:10px;font-size:14px;font-weight:700}}</style></head>
<body><div class="c"><h1>{title}</h1><p>{body}</p>
<a href="{SITE_URL}">العودة إلى نبض الصفقات</a></div></body></html>""",
        status_code=200 if ok else 404,
    )
