"""
إرسال تذكيرات مواسم التخفيضات.

يعمل مرة يومياً: يبحث عن المواسم التي تبدأ خلال PRE_DAYS يوماً أو تبدأ اليوم،
ويرسل لمشتركيها. الطوابع (`sent_pre_at` / `sent_start_at`) تمنع التكرار لو أعيد
تشغيل الخدمة أو نُفّذت الوظيفة مرتين في اليوم نفسه.

## رسالتان لا واحدة

- **قبل الموسم بأسبوع** — رسالة تخطيط: «موسمك بعد ٧ أيام، جهّز قائمتك».
- **يوم البدء** — رسالة فعل: «بدأ الآن».

الفصل مقصود: الأولى تصل وهو ما زال يقارن، والثانية تصل وهو جاهز للشراء. دمجهما
في رسالة واحدة يضيّع أحد التوقيتين.

## المواسم

تواريخ المواسم مصدرها `app/calendar/data.ts` في ريبو الويب، وهي ثابتة ميلادياً
(عدا الهجرية التقديرية). ننسخها هنا كجدول تواريخ بدء لأن الخدمة بايثون ولا تقرأ
TypeScript — وأي تعديل هناك يجب أن ينعكس هنا.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone

from api.db import get_db_context

_log = logging.getLogger("dp.season_reminders")

SITE_URL = os.getenv("SITE_URL", "https://www.dealpulseksa.com").rstrip("/")
API_URL = os.getenv("API_PUBLIC_URL", "https://api.dealpulseksa.com").rstrip("/")

# كم يوماً قبل البدء تُرسل رسالة التخطيط
PRE_DAYS = 7

# (شهر, يوم) **بداية نافذة** كل موسم — من حقل `start` في app/calendar/data.ts.
#
# ⚠️ ليست يوم الذروة. «11.11» نافذته تبدأ 9 نوفمبر، و«العودة للمدارس» 15 أغسطس
# لا 1 أغسطس. اشتقاق التواريخ من أسماء العرض بدل حقل `start` يُرسل التذكير في
# اليوم الخطأ — أخطأتُ في 8 من 12 عند أول كتابة لهذا الجدول.
#
# للتحقّق من الانحراف بعد أي تعديل في ريبو الويب:  python check_season_dates.py
SEASON_START: dict[str, tuple[int, int]] = {
    "winter-clearance": (1, 1),
    "founding-day": (2, 15),
    "ramadan": (2, 18),
    "eid-fitr": (3, 15),
    "eid-adha": (5, 20),
    "summer-sale": (6, 1),
    "back-to-school": (8, 15),
    "national-day": (9, 18),
    "riyadh-season": (10, 1),
    "eleven-eleven": (11, 9),
    "white-friday": (11, 23),
    "twelve-twelve": (12, 10),
}


def _riyadh_today() -> date:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).date()


def _seasons_due(today: date) -> tuple[list[str], list[str]]:
    """يُرجع (مواسم تبدأ بعد PRE_DAYS، مواسم تبدأ اليوم)."""
    pre_target = today + timedelta(days=PRE_DAYS)
    pre, start = [], []
    for sid, (m, d) in SEASON_START.items():
        if (m, d) == (pre_target.month, pre_target.day):
            pre.append(sid)
        if (m, d) == (today.month, today.day):
            start.append(sid)
    return pre, start


def _email_html(season_name: str, days: int, unsub_token: str) -> tuple[str, str]:
    """يُرجع (العنوان، الـHTML). `days=0` تعني أن الموسم بدأ اليوم."""
    from api.audience_sender import build_email_html

    if days > 0:
        subject = f"موسم {season_name} بعد {days} أيام"
        lead = (
            f"وصلك هذا لأنك طلبت تذكيراً بموسم <strong>{season_name}</strong>. "
            f"يبدأ بعد <strong>{days} أيام</strong> — وقت مناسب تجهّز فيه قائمتك "
            "قبل أن يبدأ الزحام."
        )
        cta = "شوف المتاجر المشاركة"
    else:
        subject = f"بدأ موسم {season_name} 🔥"
        lead = (
            f"موسم <strong>{season_name}</strong> بدأ اليوم. "
            "جمعنا لك أكواد الخصم والعروض الشغّالة في مكان واحد."
        )
        cta = "افتح العروض الآن"

    body = f"""
      <p style="margin:0 0 16px;font-size:15px;line-height:1.8;color:#334155">{lead}</p>
      <p style="margin:0 0 24px">
        <a href="{SITE_URL}/calendar"
           style="display:inline-block;background:#059669;color:#fff;text-decoration:none;
                  padding:12px 24px;border-radius:10px;font-weight:700;font-size:14px">{cta}</a>
      </p>
      <p style="margin:0;font-size:12px;color:#94a3b8;line-height:1.7">
        وصلك هذا لأنك اشتركت بتذكير هذا الموسم من تقويم نبض الصفقات.
        <a href="{API_URL}/api/v1/reminders/unsubscribe?token={unsub_token}"
           style="color:#94a3b8">إلغاء الاشتراك</a>
      </p>
    """
    return subject, build_email_html(subject, body)


def _send_batch(season_ids: list[str], kind: str, today: date) -> int:
    """kind: 'pre' أو 'start'. يُرجع عدد الرسائل المُرسلة بنجاح."""
    if not season_ids:
        return 0

    from api.audience_sender import _send_one_email

    stamp_col = "sent_pre_at" if kind == "pre" else "sent_start_at"
    days = PRE_DAYS if kind == "pre" else 0
    sent = 0

    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, email, COALESCE(season_name, season_id) AS name,
                       unsubscribe_token::text
                FROM   season_reminders
                WHERE  status = 'active'
                  AND  season_id = ANY(%s)
                  AND  season_year = %s
                  AND  {stamp_col} IS NULL
                """,
                (season_ids, today.year),
            )
            rows = cur.fetchall()

        for rid, email, name, token in rows:
            try:
                subject, html = _email_html(name, days, token)
                ok, err = _send_one_email(email, subject, html)
            except Exception as exc:  # noqa: BLE001
                ok, err = False, str(exc)

            if ok:
                sent += 1
                # نختم فقط عند النجاح — الفشل يُعاد غداً بدل أن يُفقد صامتاً.
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE season_reminders SET {stamp_col}=NOW(), updated_at=NOW() WHERE id=%s",
                        (rid,),
                    )
                conn.commit()
            else:
                _log.warning("season reminder failed for %s: %s", email, err)

    return sent


def run_season_reminders() -> dict[str, int]:
    """نقطة الدخول للجدولة. آمنة للتكرار في اليوم نفسه."""
    today = _riyadh_today()
    pre_ids, start_ids = _seasons_due(today)
    if not pre_ids and not start_ids:
        return {"pre": 0, "start": 0}

    pre_n = _send_batch(pre_ids, "pre", today)
    start_n = _send_batch(start_ids, "start", today)
    _log.info("season reminders sent — pre=%s start=%s", pre_n, start_n)
    return {"pre": pre_n, "start": start_n}
