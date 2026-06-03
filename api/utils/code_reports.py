"""
Shared core for «code report» events (Migration 029).

نقطة واحدة لتسجيل البلاغ + قاعدة السحب التلقائي + إرسال التنبيهات.
يستخدمها:
  - api/routers/track.py        (الموقع + الميني-ويب عبر HTTP)
  - deal_pulse_bot.py           (البوت مباشرة بدون HTTP)

أيّ تغيير على المنطق (عتبة 10/60 دقيقة، شكل التنبيه، snapshot الحقول)
يجب أن يتم هنا فقط.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from psycopg2.extras import RealDictCursor

from api.utils.email_alerts import send_ops_alert
from api.utils.telegram_alerts import send_telegram_alert

_log = logging.getLogger("dp.code_reports")

# قابل للتعديل عبر env بدون deployment
AUTO_SUSPEND_UNIQUE_REPORTERS = int(os.getenv("AUTO_SUSPEND_UNIQUE_REPORTERS", "10"))
AUTO_SUSPEND_WINDOW_MINUTES   = int(os.getenv("AUTO_SUSPEND_WINDOW_MINUTES",   "60"))


def _channel_ar(source: str) -> str:
    return {"web": "🌐 الموقع", "telegram_miniapp": "🔹 الميني ويب", "bot": "📱 البوت"}.get(source, source)


def _reporter_snapshot(conn, *, web_user_id: Optional[int], tg_user_id: Optional[int]) -> dict:
    info = {"name": None, "email": None, "phone": None, "telegram_username": None}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if web_user_id:
            cur.execute(
                """SELECT display_name, email, phone_number, telegram_username
                   FROM web_users WHERE id = %s""",
                (web_user_id,),
            )
            row = cur.fetchone()
            if row:
                info["name"]              = row.get("display_name")
                info["email"]             = row.get("email")
                info["phone"]             = row.get("phone_number")
                info["telegram_username"] = row.get("telegram_username")
        if tg_user_id and not info["telegram_username"]:
            cur.execute(
                """SELECT first_name, username FROM bot_users WHERE telegram_id = %s""",
                (tg_user_id,),
            )
            row = cur.fetchone()
            if row:
                if not info["name"]:
                    info["name"] = row.get("first_name")
                info["telegram_username"] = row.get("username")
    return info


def _maybe_auto_suspend(conn, store_id: str) -> tuple[bool, int]:
    """يعدّ المبلّغين الفريدين (web_user_id أو tg_user_id) خلال النافذة.
    لو ≥ العتبة → يُعلّم المتجر مسحوباً ويرجع (True, count). الفهم: المتجر
    يُسحب فقط لو لم يكن مسحوباً من قبل (للحفاظ على suspended_at الأصلي).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*)::int FROM (
                SELECT COALESCE(web_user_id::text, 'tg:' || tg_user_id::text) AS who
                FROM code_reports
                WHERE store_id = %s
                  AND created_at >= NOW() - (%s || ' minutes')::interval
                GROUP BY 1
            ) t
            """,
            (store_id, AUTO_SUSPEND_WINDOW_MINUTES),
        )
        unique_reporters = cur.fetchone()[0]

        if unique_reporters < AUTO_SUSPEND_UNIQUE_REPORTERS:
            return (False, unique_reporters)

        cur.execute(
            """
            UPDATE master
            SET    is_suspended     = TRUE,
                   suspended_at     = NOW(),
                   suspended_reason = %s
            WHERE  store_id      = %s
              AND  is_suspended  = FALSE
            RETURNING store_id
            """,
            (f"auto: {unique_reporters} reports in {AUTO_SUSPEND_WINDOW_MINUTES}min", store_id),
        )
        suspended_now = cur.fetchone() is not None
    return (suspended_now, unique_reporters)


def _send_alerts(*, store_id: str, source: str, reporter: dict,
                 public_coupon: Optional[str], issue_note: Optional[str],
                 auto_suspended: bool, unique_reporters: int) -> None:
    channel = _channel_ar(source)
    name    = reporter.get("name") or "—"
    email   = reporter.get("email") or "—"
    phone   = reporter.get("phone") or "—"
    tg_user = reporter.get("telegram_username")
    tg_disp = f"@{tg_user}" if tg_user else "—"
    coupon  = public_coupon or "—"
    note    = issue_note or "—"

    severity = "critical" if auto_suspended else "warning"
    subject  = (
        f"سحب تلقائي: {store_id} (بعد {unique_reporters} بلاغ)"
        if auto_suspended
        else f"بلاغ كود لا يعمل: {store_id}"
    )

    body_html = f"""
      <p><b>المتجر:</b> {store_id}</p>
      <p><b>الكود المُبلَّغ عنه:</b> <code>{coupon}</code></p>
      <p><b>المصدر:</b> {channel}</p>
      <hr>
      <p><b>المُبلِّغ:</b></p>
      <ul>
        <li>الاسم: {name}</li>
        <li>الإيميل: {email}</li>
        <li>الجوال: {phone}</li>
        <li>تيليجرام: {tg_disp}</li>
      </ul>
      <p><b>ملاحظة العميل:</b> {note}</p>
      <p><b>عدّاد البلاغات الفريدة آخر {AUTO_SUSPEND_WINDOW_MINUTES} دقيقة:</b>
         <b>{unique_reporters}</b> / {AUTO_SUSPEND_UNIQUE_REPORTERS}</p>
    """
    if auto_suspended:
        body_html += (
            "<p style='color:#DC2626; font-weight:bold;'>"
            "⚠️ تم سحب المتجر تلقائياً من واجهات العملاء. راجع الكود "
            "واستبدله ثم أزل السحب من «بلاغات الأكواد» في الداشبورد."
            "</p>"
        )

    try:
        send_ops_alert(subject=subject, body_html=body_html, severity=severity)
    except Exception as exc:
        _log.error("Ops email for report failed: %s", exc)

    tg_text = (
        f"*بلاغ كود لا يعمل*\n"
        f"🏪 المتجر: `{store_id}`\n"
        f"🎟 الكود: `{coupon}`\n"
        f"📡 المصدر: {channel}\n"
        f"👤 المُبلِّغ: {name} ({email}) — {tg_disp}\n"
        f"📞 الجوال: {phone}\n"
        f"📈 العدّاد: *{unique_reporters}*/{AUTO_SUSPEND_UNIQUE_REPORTERS} "
        f"خلال آخر {AUTO_SUSPEND_WINDOW_MINUTES} دقيقة"
    )
    if auto_suspended:
        tg_text = "🔴 *سحب تلقائي للمتجر*\n\n" + tg_text + "\n\n⚠️ تم إخفاؤه من العملاء."
    try:
        send_telegram_alert(text=tg_text, severity=severity)
    except Exception as exc:
        _log.error("Telegram alert for report failed: %s", exc)


def record_code_report(
    conn,
    *,
    store_id: str,
    source: str,
    web_user_id: Optional[int] = None,
    tg_user_id: Optional[int] = None,
    issue_note: Optional[str] = None,
    ip_hash: Optional[str] = None,     # hex string (يتطابق مع geo_extractor)
    ua_hash: Optional[str] = None,     # hex string
) -> dict:
    """يُسجّل بلاغ كود ويُطبّق منطق السحب التلقائي والتنبيهات.

    يفترض أن جدول master يحتوي على store_id (يفشل بالـ FK).
    يرجع dict:
      {ok, report_id, auto_suspended, unique_reporters, already_suspended}
    لا يفتح/يُغلق connection — المُتصل مسؤول عن الـ commit.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT public_coupon, is_suspended FROM master WHERE store_id = %s",
            (store_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError(f"store '{store_id}' not found")
        public_coupon = row["public_coupon"]
        already_suspended = bool(row["is_suspended"])

    reporter = _reporter_snapshot(conn, web_user_id=web_user_id, tg_user_id=tg_user_id)

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO code_reports (
                store_id, source,
                web_user_id, tg_user_id,
                reporter_name, reporter_email, reporter_phone, reporter_telegram_username,
                reported_code, issue_note,
                ip_hash, user_agent_hash
            )
            VALUES (
                %s, %s,
                %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                CASE WHEN %s IS NULL THEN NULL ELSE decode(%s, 'hex') END,
                CASE WHEN %s IS NULL THEN NULL ELSE decode(%s, 'hex') END
            )
            RETURNING id
            """,
            (
                store_id, source,
                web_user_id, tg_user_id,
                reporter["name"], reporter["email"], reporter["phone"], reporter["telegram_username"],
                public_coupon, (issue_note or None),
                ip_hash, ip_hash,
                ua_hash, ua_hash,
            ),
        )
        report_id = cur.fetchone()[0]

        if already_suspended:
            auto_suspended, unique_reporters = False, AUTO_SUSPEND_UNIQUE_REPORTERS
        else:
            auto_suspended, unique_reporters = _maybe_auto_suspend(conn, store_id)
            if auto_suspended:
                cur.execute(
                    "UPDATE code_reports SET triggered_auto_suspend = TRUE WHERE id = %s",
                    (report_id,),
                )

    _send_alerts(
        store_id=store_id, source=source, reporter=reporter,
        public_coupon=public_coupon, issue_note=issue_note,
        auto_suspended=auto_suspended, unique_reporters=unique_reporters,
    )

    return {
        "ok": True,
        "report_id": report_id,
        "auto_suspended": auto_suspended,
        "unique_reporters": unique_reporters,
        "already_suspended": already_suspended,
    }
