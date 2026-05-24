"""
Alert dispatcher — drains the pending queue from ai_alerts and emails
each one via the existing Resend → SMTP transport.

Runs every 30 seconds. Picks up to BATCH_SIZE pending alerts each pass
and processes them sequentially (Resend rate-limits us anyway).

States machine on ai_alerts.dispatch_status:
    pending  → sent     (on success — dispatched_at set)
    pending  → failed   (on exception — dispatch_error set, no retry yet)

Future enhancement: re-queue 'failed' rows older than 1 hour for retry
with exponential backoff. For Week 2 MVP, manual reset is fine.
"""
from __future__ import annotations

import logging

from api.db import get_db_context
from api.utils.email_alerts import send_ops_alert
from api.utils.telegram_alerts import send_telegram_alert

_log = logging.getLogger("dp.dispatcher")

BATCH_SIZE = 10


def dispatch_pending_alerts() -> int:
    """Send all pending alerts. Returns number successfully dispatched."""
    sent = 0
    # ساعات الهدوء (migration_016): نؤجّل الإيميل ولا نحرقه — يبقى pending
    try:
        from api.utils.ops import is_quiet_now
        quiet, label = is_quiet_now("email")
        if quiet:
            _log.info("Quiet hours active (%s) — holding email alerts as pending", label)
            return 0
    except Exception as exc:
        _log.warning("quiet-hours check skipped: %s", exc)
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                # SKIP LOCKED so multiple dispatcher instances don't fight
                # over the same row.
                cur.execute(
                    """
                    SELECT id, alert_type, severity, title, body
                    FROM ai_alerts
                    WHERE dispatch_status = 'pending'
                    ORDER BY created_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT %s
                    """,
                    (BATCH_SIZE,),
                )
                pending = cur.fetchall()

            for alert_id, _alert_type, severity, title, body in pending:
                try:
                    severity_map = {
                        "info": "info",
                        "warning": "warning",
                        "critical": "critical",
                    }
                    sev = severity_map.get(severity, "info")
                    ok = send_ops_alert(subject=title, body_html=body, severity=sev)
                    # قناة موازية: Telegram للسرعة (لا يُعتبر فشل إن لم يُهيَّأ)
                    try:
                        # نزيل HTML بسرعة لأن Telegram يفضّل نصاً
                        import re as _re
                        plain = _re.sub(r"<[^>]+>", "", body)[:800]
                        send_telegram_alert(
                            text=f"*{title}*\n\n{plain}",
                            severity=sev,
                        )
                    except Exception as _tg_exc:
                        _log.debug("telegram alert skipped: %s", _tg_exc)
                    with conn.cursor() as cur:
                        if ok:
                            cur.execute(
                                """
                                UPDATE ai_alerts
                                SET dispatch_status = 'sent',
                                    dispatched_at   = NOW(),
                                    dispatch_error  = NULL
                                WHERE id = %s
                                """,
                                (alert_id,),
                            )
                            sent += 1
                            _log.info("Alert %s dispatched (severity=%s)", alert_id, severity)
                        else:
                            cur.execute(
                                """
                                UPDATE ai_alerts
                                SET dispatch_status = 'failed',
                                    dispatch_error  = 'send_ops_alert returned False'
                                WHERE id = %s
                                """,
                                (alert_id,),
                            )
                            _log.warning("Alert %s failed (transport returned False)", alert_id)
                except Exception as exc:
                    _log.error("Alert %s exception: %s", alert_id, exc)
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            UPDATE ai_alerts
                            SET dispatch_status = 'failed',
                                dispatch_error  = %s
                            WHERE id = %s
                            """,
                            (str(exc)[:500], alert_id),
                        )
    except Exception as exc:
        _log.error("dispatch_pending_alerts top-level error: %s", exc)
        return sent

    return sent
