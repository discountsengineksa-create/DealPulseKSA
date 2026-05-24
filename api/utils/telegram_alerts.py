"""
Telegram ops alerts — قناة تنبيه ثانية (مع الإيميل، أسرع).

لماذا Telegram؟
  • وصول التنبيه خلال ثوانٍ (vs دقائق للإيميل)
  • سهولة الرد من الجوال على mentions الـ Reddit/RSS فوراً
  • مجاني تماماً (Bot API)

التهيئة:
  1. لديك BOT_TOKEN أصلاً للبوت العام (نفس التوكن)
  2. أنشئ قناة Telegram خاصة (مثلاً "DealPulse Ops")
  3. أضف البوت كـ admin في القناة
  4. احصل على chat_id (عبر @userinfobot أو forward رسالة لـ @JsonDumpBot)
  5. في Railway: OPS_TELEGRAM_CHAT_ID = -100xxxxxxxxxx

التنبيهات:
  • spike alerts (من spike_detector)
  • mentions جديدة عالية النية (من responder)
  • LLM budget warnings (من financial_guardian)

كل دالة best-effort: فشلها لا يكسر العملية الأصلية.
"""
from __future__ import annotations

import logging
import os
from typing import Literal

import requests

_log = logging.getLogger("dp.telegram_alerts")

# نشارك نفس BOT_TOKEN مع البوت العام
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
OPS_CHAT_ID = os.getenv("OPS_TELEGRAM_CHAT_ID", "").strip()

Severity = Literal["info", "warning", "critical"]
_BADGE = {"info": "🟢", "warning": "🟡", "critical": "🔴"}


def send_telegram_alert(
    *,
    text: str,
    severity: Severity = "info",
    button_url: str | None = None,
    button_label: str | None = None,
    parse_mode: str = "Markdown",
) -> bool:
    """
    يُرسل تنبيهاً لقناة الـ ops. يدعم زر inline اختياري (مثلاً للذهاب لـ
    داشبورد المراجعة).

    يرجّع True عند النجاح، False عند الفشل (مع تسجيل، بلا exception).
    """
    if not BOT_TOKEN or not OPS_CHAT_ID:
        _log.debug("Telegram ops alert skipped: BOT_TOKEN or OPS_TELEGRAM_CHAT_ID not set")
        return False

    icon = _BADGE.get(severity, "")
    payload: dict = {
        "chat_id":    OPS_CHAT_ID,
        "text":       f"{icon} *DealPulse Ops*\n\n{text}",
        "parse_mode": parse_mode,
        "disable_web_page_preview": False,
    }
    if button_url:
        payload["reply_markup"] = {
            "inline_keyboard": [[{
                "text": button_label or "افتح",
                "url":  button_url,
            }]],
        }

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload, timeout=8,
        )
        if r.status_code != 200:
            _log.warning("Telegram alert failed [%s]: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as exc:
        _log.error("Telegram alert exception: %s", str(exc)[:200])
        return False


def send_mention_alert(*, signal: dict, response_id: int | None = None,
                       admin_panel_url: str | None = None) -> bool:
    """
    تنبيه mention جديد عالي النية. signal dict من جدول social_signals.
    """
    intent = signal.get("intent_score") or 0
    severity: Severity = "critical" if intent >= 0.8 else "warning" if intent >= 0.5 else "info"

    text = (
        f"📨 *منشن جديد* — {signal.get('platform', '?')}\n"
        f"👤 من: `{signal.get('author_handle', '—')}`\n"
        f"🎯 نية: *{intent:.2f}*\n\n"
        f"_{(signal.get('content', '') or '')[:300]}_"
    )
    if signal.get("source_url"):
        text += f"\n\n🔗 [الرابط الأصلي]({signal['source_url']})"

    return send_telegram_alert(
        text=text,
        severity=severity,
        button_url=admin_panel_url,
        button_label="↗ مراجعة الرد",
    )


def send_spike_alert(*, store_id: str, score: float, message: str,
                     admin_panel_url: str | None = None) -> bool:
    """تنبيه spike (زيادة مفاجئة في نشاط متجر)."""
    text = (
        f"🚀 *Spike Alert*\n"
        f"🏪 المتجر: `{store_id}`\n"
        f"📈 z-score: *{score:.1f}*\n\n"
        f"{message}"
    )
    return send_telegram_alert(
        text=text,
        severity="critical",
        button_url=admin_panel_url,
        button_label="↗ افتح الداشبورد",
    )
