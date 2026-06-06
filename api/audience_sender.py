"""
محرّك الإرسال الفعلي للشرائح (Audience Sender).

يأخذ شريحة + رسالة → يجلب المستلمين → يرسل (تليجرام/بريد) →
يسجّل كل مستلم على حدة → يحدّث aggregates.

الميزات:
  • Telegram عبر Bot API (sendMessage / sendPhoto)
  • البريد عبر Resend (مع SMTP fallback)
  • Throttling: تأخير قابل للضبط بين الرسائل
  • Batching: مسلسل لتفادي rate-limit
  • A/B variants: قسمة تلقائية 50/50
  • Per-recipient log في broadcast_recipients
  • Frequency cap اختياري (max_per_day_per_user)
  • Dry-run للاختبار بدون إرسال فعلي

API:
    send_telegram_broadcast(conn, segment_id, message_text, ...) -> dict
    send_email_broadcast(conn, segment_id, subject, body_html, ...) -> dict
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import socket
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable

import requests

from api import audience_engine as _ae
from api.utils import broadcast_tracker as _bt

_log = logging.getLogger("dp.audience_sender")

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")

# الحدود الافتراضية (يمكن تخصيصها لكل نداء)
DEFAULT_TG_RATE_PER_SEC    = 20         # Telegram: حد 30/sec — نبقى تحت السقف
DEFAULT_EMAIL_RATE_PER_SEC = 8          # Resend: 10/sec للفرع المجاني عادةً
DEFAULT_BATCH_SIZE         = 100


# ════════════════════════════════════════════════════════════════════════════
# Email helpers (نسخة من dashboard.py لتعمل خارج Streamlit)
# ════════════════════════════════════════════════════════════════════════════

def _send_one_email(to_email: str, subject: str, html_body: str) -> tuple[bool, str | None]:
    """Resend أولاً، ثم SMTP. يرجّع (success, error_msg)."""
    resend_key = os.getenv("RESEND_API_KEY")
    smtp_user  = os.getenv("SMTP_USER")
    smtp_pass  = (os.getenv("SMTP_PASS") or "").replace(" ", "")
    smtp_host  = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port  = int(os.getenv("SMTP_PORT", "587"))
    smtp_from  = os.getenv("SMTP_FROM", smtp_user or "onboarding@resend.dev")
    from_name  = os.getenv("SMTP_FROM_NAME", "نبض الصفقات")

    if resend_key:
        try:
            resp = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}",
                         "Content-Type": "application/json"},
                json={"from": f"{from_name} <{smtp_from}>",
                      "to": [to_email], "subject": subject, "html": html_body},
                timeout=15,
            )
            if resp.status_code in (200, 201, 202):
                return True, None
            return False, f"Resend HTTP {resp.status_code}: {resp.text[:200]}"
        except Exception as e:
            return False, f"Resend exception: {type(e).__name__}: {str(e)[:200]}"

    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{from_name} <{smtp_from}>"
            msg["To"]      = to_email
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            ipv4 = socket.gethostbyname(smtp_host)
            if smtp_port == 465:
                with smtplib.SMTP_SSL(ipv4, smtp_port, timeout=20) as srv:
                    srv.login(smtp_user, smtp_pass)
                    srv.send_message(msg)
            else:
                with smtplib.SMTP(ipv4, smtp_port, timeout=20) as srv:
                    srv.ehlo(); srv.starttls(); srv.ehlo()
                    srv.login(smtp_user, smtp_pass)
                    srv.send_message(msg)
            return True, None
        except Exception as e:
            return False, f"SMTP exception: {type(e).__name__}: {str(e)[:200]}"
    return False, "لا RESEND_API_KEY ولا SMTP_USER/SMTP_PASS مُعرَّفة"


def build_email_html(subject: str, body_html: str, banner_url: str = "") -> str:
    """قالب البريد الكامل (نسخة من dashboard.py)."""
    banner_tag = (
        f'<img src="{banner_url}" style="width:100%;border-radius:8px;'
        f'margin-bottom:24px;display:block;" />'
        if banner_url else "")
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#F5F5F0;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#F5F5F0;padding:32px 16px;">
  <tr><td>
    <table width="600" cellpadding="0" cellspacing="0" align="center"
           style="background:#FFFFFF;border-radius:16px;overflow:hidden;
                  box-shadow:0 4px 24px rgba(0,0,0,0.07);max-width:100%;">
      <tr>
        <td style="background:linear-gradient(135deg,#10B981,#059669);
                   padding:28px 40px;text-align:center;">
          <h1 style="color:white;margin:0;font-size:22px;font-weight:700;">نبض الصفقات 🌐</h1>
          <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">dealpulseksa.com</p>
        </td>
      </tr>
      <tr>
        <td style="padding:32px 40px;font-size:15px;color:#1F2937;line-height:1.7;">
          {banner_tag}
          {body_html}
        </td>
      </tr>
      <tr>
        <td style="background:#F5F5F0;padding:20px 40px;text-align:center;
                   border-top:1px solid #E5E7EB;">
          <p style="color:#9CA3AF;font-size:12px;margin:0;">
            نبض الصفقات | Deal Pulse KSA<br>
            <a href="https://dealpulseksa.com"
               style="color:#10B981;text-decoration:none;">dealpulseksa.com</a>
          </p>
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body></html>"""


# ════════════════════════════════════════════════════════════════════════════
# Telegram helpers
# ════════════════════════════════════════════════════════════════════════════

def _send_one_telegram(chat_id: str, text: str,
                       image_url: str | None = None) -> tuple[bool, str | None]:
    """يرسل رسالة تليجرام (مع صورة اختيارية). يرجّع (success, error_msg)."""
    if not BOT_TOKEN:
        return False, "BOT_TOKEN غير مُعرَّف في البيئة"

    try:
        if image_url:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
            payload = {"chat_id": chat_id, "photo": image_url, "caption": text,
                       "parse_mode": "HTML"}
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": False}
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            return True, None
        if r.status_code == 429:
            # Too Many Requests: نقرأ retry_after لكن نرجّع فشلاً يعالجه caller
            return False, f"rate_limit_429: {r.text[:200]}"
        if r.status_code == 403:
            return False, "user_blocked_bot (403)"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, f"exception: {type(e).__name__}: {str(e)[:200]}"


# ════════════════════════════════════════════════════════════════════════════
# Audience resolution + filtering helpers
# ════════════════════════════════════════════════════════════════════════════

def _resolve_audience(conn, segment_id: int | None,
                      rules_json: dict | None, channel: str) -> list[dict]:
    """يجلب قائمة المستلمين (مع تطبيق الاستثناءات)."""
    if segment_id and not rules_json:
        seg = _ae.load_segment(conn, segment_id)
        if not seg:
            raise ValueError(f"شريحة #{segment_id} غير موجودة")
        rules_json = seg["rules_json"]
    return _ae.fetch_audience(conn, channel, rules_json or {},
                              apply_exclusions=True)


def _filter_frequency_cap(conn, recipients: list[dict], channel: str,
                          cap_per_day: int) -> tuple[list[dict], int]:
    """يستبعد المستلمين اللي تجاوزوا cap رسائل اليوم.

    يرجّع (المستلمون المؤهلون، عدد المتجاوزين).
    """
    if cap_per_day <= 0 or not recipients:
        return recipients, 0
    identifiers = []
    for r in recipients:
        ident = (r.get("user_id") if channel == "telegram"
                 else r.get("email"))
        if ident:
            identifiers.append(str(ident))
    if not identifiers:
        return recipients, 0
    placeholders = ", ".join(["%s"] * len(identifiers))
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT user_identifier, COUNT(*) FROM broadcast_recipients "
            f"WHERE broadcast_kind = %s AND status IN ('sent','opened','clicked') "
            f"AND sent_at >= NOW() - INTERVAL '1 day' "
            f"AND user_identifier IN ({placeholders}) "
            f"GROUP BY user_identifier HAVING COUNT(*) >= %s",
            [channel] + identifiers + [cap_per_day],
        )
        over_cap = {r[0] for r in cur.fetchall()}
    if not over_cap:
        return recipients, 0
    kept = []
    for r in recipients:
        ident = str(r.get("user_id") if channel == "telegram" else r.get("email"))
        if ident not in over_cap:
            kept.append(r)
    return kept, len(over_cap)


def _split_ab(recipients: list[dict]) -> tuple[list[dict], list[dict]]:
    """يقسّم القائمة 50/50 إلى مجموعتي A و B."""
    if not recipients:
        return [], []
    mid = len(recipients) // 2
    return recipients[:mid], recipients[mid:]


# ════════════════════════════════════════════════════════════════════════════
# Public API — Telegram
# ════════════════════════════════════════════════════════════════════════════

def send_telegram_broadcast(
    conn,
    *,
    segment_id: int | None = None,
    rules_json: dict | None = None,
    message_text: str,
    image_url: str | None = None,
    variant_b_text: str | None = None,
    rate_per_sec: int = DEFAULT_TG_RATE_PER_SEC,
    batch_size: int = DEFAULT_BATCH_SIZE,
    freq_cap_per_day: int = 3,
    sent_by: str = "",
    dry_run: bool = False,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict:
    """يرسل حملة تليجرام كاملة، يرجّع نتائج إجمالية.

    progress_cb(done, total) يُستدعى بعد كل مستلم (لتحديث UI).
    """
    if not message_text and not variant_b_text:
        raise ValueError("لا توجد رسالة")

    recipients = _resolve_audience(conn, segment_id, rules_json, "telegram")
    initial = len(recipients)

    # frequency cap
    recipients, skipped = _filter_frequency_cap(conn, recipients,
                                                "telegram", freq_cap_per_day)
    # A/B split
    if variant_b_text:
        group_a, group_b = _split_ab(recipients)
    else:
        group_a, group_b = recipients, []

    if dry_run:
        return {
            "dry_run": True, "would_send": len(group_a) + len(group_b),
            "initial": initial, "skipped_freq_cap": skipped,
            "variant_a": len(group_a), "variant_b": len(group_b),
        }

    # سجّل الحملة في broadcast_logs
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO broadcast_logs "
            "(message_text, image_url, target_audience, delivery_count, "
            " segment_id, rules_snapshot, status, "
            " variant_a_text, variant_b_text, sent_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,'sending',%s,%s,%s) RETURNING id",
            (message_text, image_url,
             f"segment:{segment_id}" if segment_id else "custom",
             len(group_a) + len(group_b),
             segment_id,
             json.dumps(rules_json or {}, ensure_ascii=False) if rules_json else None,
             message_text, variant_b_text, sent_by),
        )
        broadcast_id = cur.fetchone()[0]
        conn.commit()

    # سجّل المستلمين كـ queued (مع tracking_token لكل واحد)
    # نحفظ token لكل uid في dict لاستخدامه في إعادة كتابة الـURLs لاحقاً
    tokens_by_uid: dict[str, str] = {}
    with conn.cursor() as cur:
        for grp, var in ((group_a, "A"), (group_b, "B")):
            for r in grp:
                uid = str(r.get("user_id") or "")
                if not uid:
                    continue
                tok = _bt.generate_token()
                tokens_by_uid[uid] = tok
                cur.execute(
                    "INSERT INTO broadcast_recipients "
                    "(broadcast_id, broadcast_kind, user_identifier, user_db_id, "
                    " variant, tracking_token) VALUES (%s,'telegram',%s,%s,%s,%s)",
                    (broadcast_id, uid, uid, var if variant_b_text else None, tok),
                )
        conn.commit()

    # سجّل URLs الحملة (للنصّين A و B) → ترجع {url: link_id}
    all_urls = set(_bt.extract_urls(message_text or ""))
    if variant_b_text:
        all_urls.update(_bt.extract_urls(variant_b_text))
    url_to_id = _bt.register_links(conn, broadcast_id=broadcast_id,
                                    broadcast_kind="telegram", urls=all_urls)

    # الإرسال الفعلي
    delay = max(0.01, 1.0 / max(1, rate_per_sec))
    sent_ok = sent_fail = 0
    total_to_send = len(group_a) + len(group_b)
    done = 0

    for grp, text in ((group_a, message_text),
                      (group_b, variant_b_text or message_text)):
        for r in grp:
            uid = str(r.get("user_id") or "")
            if not uid:
                continue
            # أعد كتابة الـURLs لتمر عبر tracker (لو tracking مفعّل)
            tok = tokens_by_uid.get(uid)
            personalized_text = (
                _bt.rewrite_body_for_recipient(
                    text, tracking_token=tok, url_to_id=url_to_id, is_html=False)
                if tok and url_to_id and _bt.is_tracking_enabled()
                else text
            )
            ok, err = _send_one_telegram(uid, personalized_text, image_url=image_url)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE broadcast_recipients "
                    "SET status=%s, sent_at=NOW(), error_message=%s "
                    "WHERE broadcast_id=%s AND user_identifier=%s "
                    "AND broadcast_kind='telegram'",
                    ("sent" if ok else "failed", err, broadcast_id, uid),
                )
                # تتبّع المحظورين: 403 = حظر دائم → علّم المستخدم
                if not ok and err and ("403" in err or "user_blocked_bot" in err
                                       or "chat not found" in err.lower()):
                    cur.execute(
                        "UPDATE bot_users SET telegram_blocked_at = COALESCE(telegram_blocked_at, NOW()), "
                        "last_telegram_error = %s WHERE telegram_id::text = %s",
                        (err[:500], uid),
                    )
                elif not ok and err:
                    # خطأ غير حظر — سجّل آخر خطأ فقط (بدون رفع راية الحظر)
                    cur.execute(
                        "UPDATE bot_users SET last_telegram_error = %s "
                        "WHERE telegram_id::text = %s",
                        (err[:500], uid),
                    )
                elif ok:
                    # نجاح بعد فشل سابق → امسح راية الحظر (مستخدم رجع)
                    cur.execute(
                        "UPDATE bot_users SET telegram_blocked_at = NULL, "
                        "last_telegram_error = NULL "
                        "WHERE telegram_id::text = %s AND telegram_blocked_at IS NOT NULL",
                        (uid,),
                    )
                conn.commit()
            if ok:
                sent_ok += 1
            else:
                sent_fail += 1
            done += 1
            if progress_cb:
                try:
                    progress_cb(done, total_to_send)
                except Exception:
                    pass
            time.sleep(delay)

    # تحديث aggregates
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE broadcast_logs SET sent_count=%s, failed_count=%s, "
            "status=%s WHERE id=%s",
            (sent_ok, sent_fail,
             "completed" if sent_fail == 0 else "partial",
             broadcast_id),
        )
        conn.commit()

    if segment_id:
        _ae.mark_segment_used(conn, segment_id)

    return {
        "broadcast_id": broadcast_id,
        "sent": sent_ok, "failed": sent_fail,
        "initial": initial, "skipped_freq_cap": skipped,
        "variant_a": len(group_a), "variant_b": len(group_b),
    }


# ════════════════════════════════════════════════════════════════════════════
# Public API — Email
# ════════════════════════════════════════════════════════════════════════════

def send_email_broadcast(
    conn,
    *,
    segment_id: int | None = None,
    rules_json: dict | None = None,
    subject: str,
    body_html: str,
    banner_url: str = "",
    variant_b_subject: str | None = None,
    variant_b_html: str | None = None,
    rate_per_sec: int = DEFAULT_EMAIL_RATE_PER_SEC,
    batch_size: int = DEFAULT_BATCH_SIZE,
    freq_cap_per_day: int = 3,
    sent_by: str = "",
    dry_run: bool = False,
    progress_cb: Callable[[int, int], None] | None = None,
) -> dict:
    """يرسل حملة بريد كاملة."""
    if not subject or not body_html:
        raise ValueError("subject + body_html مطلوبان")

    recipients = _resolve_audience(conn, segment_id, rules_json, "email")
    initial = len(recipients)

    recipients, skipped = _filter_frequency_cap(conn, recipients,
                                                "email", freq_cap_per_day)
    if variant_b_html:
        group_a, group_b = _split_ab(recipients)
    else:
        group_a, group_b = recipients, []

    if dry_run:
        return {
            "dry_run": True, "would_send": len(group_a) + len(group_b),
            "initial": initial, "skipped_freq_cap": skipped,
            "variant_a": len(group_a), "variant_b": len(group_b),
        }

    # سجّل الحملة في email_logs
    full_html_a = build_email_html(subject, body_html, banner_url)
    full_html_b = (build_email_html(variant_b_subject or subject,
                                    variant_b_html or body_html,
                                    banner_url)
                   if variant_b_html else None)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO email_logs "
            "(subject, body_html, banner_url, target_audience, delivery_count, "
            " segment_id, rules_snapshot, status, sent_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,'sending',%s) RETURNING id",
            (subject, full_html_a, banner_url,
             f"segment:{segment_id}" if segment_id else "custom",
             len(group_a) + len(group_b), segment_id,
             json.dumps(rules_json or {}, ensure_ascii=False) if rules_json else None,
             sent_by),
        )
        email_log_id = cur.fetchone()[0]
        conn.commit()

    # سجّل المستلمين مع tracking_token لكل واحد
    tokens_by_email: dict[str, str] = {}
    with conn.cursor() as cur:
        for grp, var in ((group_a, "A"), (group_b, "B")):
            for r in grp:
                email = r.get("email")
                if not email:
                    continue
                tok = _bt.generate_token()
                tokens_by_email[email] = tok
                cur.execute(
                    "INSERT INTO broadcast_recipients "
                    "(broadcast_id, broadcast_kind, user_identifier, user_db_id, "
                    " variant, tracking_token) VALUES (%s,'email',%s,%s,%s,%s)",
                    (email_log_id, email, str(r.get("user_id") or ""),
                     var if variant_b_html else None, tok),
                )
        conn.commit()

    # سجّل URLs في full_html_a + full_html_b للبحث السريع لاحقاً
    all_urls = set(_bt.extract_urls(full_html_a or ""))
    if full_html_b:
        all_urls.update(_bt.extract_urls(full_html_b))
    url_to_id = _bt.register_links(conn, broadcast_id=email_log_id,
                                    broadcast_kind="email", urls=all_urls)
    tracking_on = bool(url_to_id) and _bt.is_tracking_enabled()

    delay = max(0.01, 1.0 / max(1, rate_per_sec))
    sent_ok = sent_fail = 0
    total_to_send = len(group_a) + len(group_b)
    done = 0

    for grp, subj, html in (
        (group_a, subject, full_html_a),
        (group_b, variant_b_subject or subject, full_html_b or full_html_a),
    ):
        for r in grp:
            email = r.get("email")
            if not email:
                continue
            # شخصنة الـHTML: استبدل URLs بـ tracked + احقن pixel
            tok = tokens_by_email.get(email)
            if tok and _bt.is_tracking_enabled():
                personalized_html = (
                    _bt.rewrite_body_for_recipient(
                        html, tracking_token=tok, url_to_id=url_to_id,
                        is_html=True)
                    if tracking_on else html
                )
                personalized_html = _bt.inject_open_pixel(personalized_html, tok)
            else:
                personalized_html = html
            ok, err = _send_one_email(email, subj, personalized_html)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE broadcast_recipients "
                    "SET status=%s, sent_at=NOW(), error_message=%s "
                    "WHERE broadcast_id=%s AND user_identifier=%s "
                    "AND broadcast_kind='email'",
                    ("sent" if ok else "failed", err, email_log_id, email),
                )
                conn.commit()
            if ok:
                sent_ok += 1
            else:
                sent_fail += 1
            done += 1
            if progress_cb:
                try:
                    progress_cb(done, total_to_send)
                except Exception:
                    pass
            time.sleep(delay)

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE email_logs SET sent_count=%s, failed_count=%s, "
            "status=%s WHERE id=%s",
            (sent_ok, sent_fail,
             "completed" if sent_fail == 0 else "partial",
             email_log_id),
        )
        conn.commit()

    if segment_id:
        _ae.mark_segment_used(conn, segment_id)

    return {
        "broadcast_id": email_log_id,
        "sent": sent_ok, "failed": sent_fail,
        "initial": initial, "skipped_freq_cap": skipped,
        "variant_a": len(group_a), "variant_b": len(group_b),
    }


# ════════════════════════════════════════════════════════════════════════════
# Exclusions management
# ════════════════════════════════════════════════════════════════════════════

def add_exclusion(conn, *, channel: str, user_identifier: str,
                  reason: str = "", added_by: str = "") -> None:
    """أضف مستخدم لقائمة الاستثناء (don't-send)."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO broadcast_exclusions "
            "(channel, user_identifier, reason, added_by) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (channel, user_identifier) DO NOTHING",
            (channel, user_identifier, reason, added_by),
        )
        conn.commit()


def remove_exclusion(conn, *, channel: str, user_identifier: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM broadcast_exclusions "
            "WHERE channel = %s AND user_identifier = %s",
            (channel, user_identifier),
        )
        conn.commit()


# ════════════════════════════════════════════════════════════════════════════
# Anti-spam: منع تكرار نفس الرسالة لنفس الشريحة
# ════════════════════════════════════════════════════════════════════════════

def check_recent_duplicate(conn, *, segment_id: int | None,
                           message_text: str, channel: str,
                           within_hours: int = 24) -> bool:
    """يرجّع True لو نفس الرسالة أُرسلت لنفس الشريحة خلال آخر X ساعة."""
    if not segment_id or not message_text:
        return False
    table = "broadcast_logs" if channel == "telegram" else "email_logs"
    msg_col = "message_text" if channel == "telegram" else "subject"
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT 1 FROM {table} WHERE segment_id = %s AND {msg_col} = %s "
            f"AND sent_at >= NOW() - (%s || ' hours')::INTERVAL "
            f"AND status IN ('completed','partial','sending') LIMIT 1",
            (segment_id, message_text, str(within_hours)),
        )
        return cur.fetchone() is not None


# ════════════════════════════════════════════════════════════════════════════
# Scheduling
# ════════════════════════════════════════════════════════════════════════════

def schedule_broadcast(conn, *, name: str, segment_id: int, channel: str,
                       message_payload: dict, schedule_type: str,
                       run_at: str | None = None, cron_expr: str | None = None,
                       timezone: str = "Asia/Riyadh",
                       created_by: str = "") -> int:
    """ينشئ جدول إرسال (once أو متكرر).

    message_payload أمثلة:
      Telegram: {"text":"...","image_url":"..."}
      Email:    {"subject":"...","body_html":"...","banner_url":"..."}
    """
    if schedule_type not in ("once","daily","weekly","custom_cron"):
        raise ValueError(f"schedule_type غير مدعوم: {schedule_type}")
    if channel not in ("telegram","email"):
        raise ValueError(f"channel غير مدعوم: {channel}")
    # احسب next_run_at
    next_run = run_at
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO broadcast_schedules "
            "(name, segment_id, channel, message_payload, schedule_type, "
            " run_at, cron_expr, timezone, next_run_at, created_by) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (name, segment_id, channel,
             json.dumps(message_payload, ensure_ascii=False),
             schedule_type, run_at, cron_expr, timezone, next_run, created_by),
        )
        sid = cur.fetchone()[0]
        conn.commit()
        return sid


def list_schedules(conn, *, enabled_only: bool = False) -> list[dict]:
    with conn.cursor() as cur:
        where = " WHERE enabled = TRUE" if enabled_only else ""
        cur.execute(
            f"SELECT s.id, s.name, s.segment_id, sg.name AS segment_name, "
            f"s.channel, s.schedule_type, s.run_at, s.cron_expr, "
            f"s.enabled, s.last_run_at, s.next_run_at, s.created_at "
            f"FROM broadcast_schedules s "
            f"LEFT JOIN audience_segments sg ON sg.id = s.segment_id"
            f"{where} ORDER BY s.next_run_at NULLS LAST, s.id DESC"
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def toggle_schedule(conn, schedule_id: int, enabled: bool) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE broadcast_schedules SET enabled = %s WHERE id = %s",
            (enabled, schedule_id),
        )
        conn.commit()


def delete_schedule(conn, schedule_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM broadcast_schedules WHERE id = %s",
                    (schedule_id,))
        conn.commit()


def process_due_schedules(conn, *, now_utc=None) -> list[dict]:
    """يشغّل كل الجداول المستحقّة (next_run_at <= NOW).

    يُفترض أن يُستدعى من cron أو worker كل دقيقة. يرجّع نتائج الإرسال.
    """
    results = []
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, segment_id, channel, message_payload, schedule_type, "
            "run_at FROM broadcast_schedules "
            "WHERE enabled = TRUE AND next_run_at IS NOT NULL "
            "AND next_run_at <= NOW()"
        )
        due = cur.fetchall()
    for row in due:
        sid_sched, seg_id, channel, payload_raw, sched_type, run_at = row
        payload = payload_raw if isinstance(payload_raw, dict) else json.loads(payload_raw)
        try:
            if channel == "telegram":
                res = send_telegram_broadcast(
                    conn, segment_id=seg_id,
                    message_text=payload.get("text",""),
                    image_url=payload.get("image_url"),
                    sent_by=f"schedule:{sid_sched}")
            else:
                res = send_email_broadcast(
                    conn, segment_id=seg_id,
                    subject=payload.get("subject",""),
                    body_html=payload.get("body_html",""),
                    banner_url=payload.get("banner_url",""),
                    sent_by=f"schedule:{sid_sched}")
            results.append({"schedule_id": sid_sched, **res})
        except Exception as e:
            results.append({"schedule_id": sid_sched, "error": str(e)})
        # حدّث الجدول: last_run_at + next_run_at
        with conn.cursor() as cur:
            if sched_type == "once":
                cur.execute(
                    "UPDATE broadcast_schedules SET last_run_at=NOW(), "
                    "next_run_at=NULL, enabled=FALSE WHERE id=%s",
                    (sid_sched,))
            elif sched_type == "daily":
                cur.execute(
                    "UPDATE broadcast_schedules SET last_run_at=NOW(), "
                    "next_run_at = NOW() + INTERVAL '1 day' WHERE id=%s",
                    (sid_sched,))
            elif sched_type == "weekly":
                cur.execute(
                    "UPDATE broadcast_schedules SET last_run_at=NOW(), "
                    "next_run_at = NOW() + INTERVAL '7 days' WHERE id=%s",
                    (sid_sched,))
            conn.commit()
    return results


# ════════════════════════════════════════════════════════════════════════════
# Post-send detailed reports
# ════════════════════════════════════════════════════════════════════════════

def broadcast_report(conn, broadcast_id: int, channel: str) -> dict:
    """تقرير مفصّل لحملة: إجماليات + status + CTR + Open rate + top links."""
    table = "broadcast_logs" if channel == "telegram" else "email_logs"
    out: dict = {"broadcast_id": broadcast_id, "channel": channel}
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT delivery_count, sent_count, failed_count, status, "
            f"sent_at, segment_id FROM {table} WHERE id = %s",
            (broadcast_id,))
        row = cur.fetchone()
        if not row:
            return {"error": "حملة غير موجودة"}
        out.update({
            "delivery_count": row[0], "sent_count": row[1],
            "failed_count": row[2], "status": row[3],
            "sent_at": row[4], "segment_id": row[5],
        })

        # توزيع حسب status
        cur.execute(
            "SELECT status, COUNT(*) FROM broadcast_recipients "
            "WHERE broadcast_id = %s AND broadcast_kind = %s GROUP BY status",
            (broadcast_id, channel))
        out["by_status"] = dict(cur.fetchall())

        # إحصاء فتح وكليك (الجديد)
        cur.execute(
            "SELECT "
            "  COUNT(*) FILTER (WHERE open_count > 0)        AS unique_opens, "
            "  COUNT(*) FILTER (WHERE click_count > 0)       AS unique_clicks, "
            "  COALESCE(SUM(open_count),0)                   AS total_opens, "
            "  COALESCE(SUM(click_count),0)                  AS total_clicks "
            "FROM broadcast_recipients "
            "WHERE broadcast_id = %s AND broadcast_kind = %s",
            (broadcast_id, channel))
        eng = cur.fetchone()
        out["engagement"] = {
            "unique_opens":  int(eng[0] or 0),
            "unique_clicks": int(eng[1] or 0),
            "total_opens":   int(eng[2] or 0),
            "total_clicks":  int(eng[3] or 0),
        }
        sent = int(out.get("sent_count") or 0) or 1
        # القنوات: الإيميل وحده يدعم Open rate (pixel). التليجرام = N/A.
        out["engagement"]["open_rate"]  = (
            round(out["engagement"]["unique_opens"]  / sent * 100, 2)
            if channel == "email" else None)
        out["engagement"]["click_rate"] = round(
            out["engagement"]["unique_clicks"] / sent * 100, 2)

        # توزيع حسب variant (A/B) — مع CTR لكل نسخة
        cur.execute(
            "SELECT variant, "
            "       COUNT(*)                                    AS total, "
            "       COUNT(*) FILTER (WHERE status='sent' OR status='opened' OR status='clicked') AS sent, "
            "       COUNT(*) FILTER (WHERE open_count > 0)      AS opens, "
            "       COUNT(*) FILTER (WHERE click_count > 0)     AS clicks "
            "FROM broadcast_recipients "
            "WHERE broadcast_id = %s AND broadcast_kind = %s "
            "AND variant IS NOT NULL GROUP BY variant ORDER BY variant",
            (broadcast_id, channel))
        by_var: dict = {}
        for v, total, sent_v, opens, clicks in cur.fetchall():
            sent_v = sent_v or 0
            base = sent_v if sent_v else 1
            by_var[v] = {
                "total": int(total), "sent": int(sent_v),
                "opens": int(opens), "clicks": int(clicks),
                "open_rate":  round(opens/base*100, 2) if channel == "email" else None,
                "click_rate": round(clicks/base*100, 2),
            }
        out["by_variant"] = by_var

        # أعلى الروابط نقراً (لو في tracking)
        cur.execute(
            "SELECT lt.original_url, COUNT(c.id) AS clicks, "
            "       COUNT(DISTINCT c.recipient_id) AS unique_clickers "
            "FROM broadcast_link_targets lt "
            "LEFT JOIN broadcast_link_clicks c ON c.link_target_id = lt.id "
            "WHERE lt.broadcast_id = %s AND lt.broadcast_kind = %s "
            "GROUP BY lt.original_url ORDER BY clicks DESC LIMIT 10",
            (broadcast_id, channel))
        out["top_links"] = [
            {"url": r[0], "clicks": int(r[1] or 0),
             "unique_clickers": int(r[2] or 0)}
            for r in cur.fetchall()
        ]

        # عيّنة من الفاشلين مع أسباب الفشل
        cur.execute(
            "SELECT user_identifier, error_message FROM broadcast_recipients "
            "WHERE broadcast_id = %s AND broadcast_kind = %s "
            "AND status = 'failed' LIMIT 10",
            (broadcast_id, channel))
        out["failure_samples"] = [{"user": r[0], "error": r[1]} for r in cur.fetchall()]
    return out


def list_blocked_telegram_users(conn, limit: int = 100) -> list[dict]:
    """قائمة مستخدمي البوت اللي حُظروا تلقائياً (آخر 100)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT telegram_id::text AS telegram_id, username, "
            "telegram_blocked_at, last_telegram_error "
            "FROM bot_users WHERE telegram_blocked_at IS NOT NULL "
            "AND deleted_at IS NULL "
            "ORDER BY telegram_blocked_at DESC LIMIT %s",
            (limit,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def unblock_telegram_user(conn, telegram_id: str) -> bool:
    """يُلغي وسم الحظر يدوياً (لو الأدمن يعتقد أن المستخدم رجع للبوت)."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE bot_users SET telegram_blocked_at = NULL, "
            "last_telegram_error = NULL "
            "WHERE telegram_id::text = %s",
            (telegram_id,),
        )
        conn.commit()
        return cur.rowcount > 0


def list_exclusions(conn, channel: str | None = None) -> list[dict]:
    with conn.cursor() as cur:
        if channel:
            cur.execute(
                "SELECT id, channel, user_identifier, reason, added_at, added_by "
                "FROM broadcast_exclusions WHERE channel IN (%s,'both') "
                "ORDER BY added_at DESC",
                (channel,),
            )
        else:
            cur.execute(
                "SELECT id, channel, user_identifier, reason, added_at, added_by "
                "FROM broadcast_exclusions ORDER BY added_at DESC"
            )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


__all__ = [
    "send_telegram_broadcast",
    "send_email_broadcast",
    "build_email_html",
    "add_exclusion",
    "remove_exclusion",
    "list_exclusions",
    "list_blocked_telegram_users",
    "unblock_telegram_user",
    "check_recent_duplicate",
    "schedule_broadcast",
    "list_schedules",
    "toggle_schedule",
    "delete_schedule",
    "process_due_schedules",
    "broadcast_report",
]
