"""
Platform digest worker — invoked by APScheduler on two cron schedules:

  • run_directive_cycle("daily")   — 07:00 Riyadh, every day.
      Pure data pulse: platform-health snapshot + Search Console (GSC)
      performance vs last week. NO LLM call. Always sends (it is the
      daily heartbeat the owner reads to know status).

  • run_directive_cycle("weekly")  — 07:30 Riyadh, Mondays.
      Everything the daily has + 4-week search trend + LLM strategic
      directives (wider 7-day snapshot). Sends even with zero directives
      because the trend content stands on its own.

Design notes:
  • The old every-3h cadence produced near-duplicate emails (6h cache,
    thin data) and frequently mailed an empty "توجيهات AI" body. Daily
    has no LLM so it can never be empty; weekly always carries trends.
  • Model / token / cost lines were removed from the email — that is
    dev telemetry, it lives on the dashboard («متابعة المنصة»).

Failures are logged, never raised — the scheduler stays healthy
regardless of LLM or DB availability.
"""
from __future__ import annotations

import logging
from typing import Any

from api.utils.email_alerts import send_ops_alert
from api.utils.llm_service import generate_directive

_log = logging.getLogger("dp.directive")


def _render_directives_html(result: dict[str, Any]) -> str:
    """Render the LLM directive list as an Arabic HTML fragment (weekly only)."""
    directives = result.get("directives") or []
    if not directives:
        return ""

    parts = ["<h3 style='color:#059669;margin:18px 0 10px;'>🧭 التوجيهات التشغيلية</h3>"]
    for i, d in enumerate(directives, 1):
        prio = d.get("priority", "medium")
        color = {"high": "#DC2626", "medium": "#F59E0B", "low": "#10B981"}.get(prio, "#6B7280")
        action = d.get("action", "")
        rationale = d.get("rationale", "")
        ids = d.get("affected_master_ids") or []
        parts.append(
            f"<div style='border-right:4px solid {color};padding:8px 14px;"
            f"margin:8px 0;background:#F9FAFB;border-radius:6px;'>"
            f"<div style='font-weight:700;color:{color};'>#{i} · {prio.upper()}</div>"
            f"<div style='margin:6px 0;'>{action}</div>"
            f"<div style='color:#6B7280;font-size:13px;'>{rationale}</div>"
            + (f"<div style='color:#9CA3AF;font-size:12px;margin-top:4px;'>متاجر: {ids}</div>" if ids else "")
            + "</div>"
        )
    return "".join(parts)


def _health_urgent(health: dict[str, Any]) -> bool:
    """هل في اللقطة إشارة تستحق شارة تحذير (توقّف/تهديد/قفزة)؟"""
    site = health.get("site") or {}
    sec = health.get("security") or {}
    spike = health.get("spike") or {}
    return bool(
        site.get("degraded") or site.get("possible_outage")
        or sec.get("threats_24h") or sec.get("blacklist_24h")
        or spike.get("is_spike")
    )


def run_directive_cycle(mode: str = "daily") -> None:
    """دورة تقرير واحدة. mode = 'daily' (بيانات فقط) أو 'weekly' (بيانات + LLM).

    يحترم مفتاح الإيقاف في platform_settings:
      • directive_enabled='0'  → تخطّي كامل
      • directive_recipient    → بريد مستلِم بديل (فارغ = الافتراضي)
    (تقييد directive_min_hours أُلغي — الـ cron صار يتحكّم بالإيقاع.)
    """
    weekly = mode == "weekly"
    recipient: str | None = None
    try:
        from api.utils.settings import get_setting
        if get_setting("directive_enabled", "1") != "1":
            _log.info("Digest disabled via platform_settings — skipping")
            return
        recipient = (get_setting("directive_recipient", "") or "").strip() or None
    except Exception as exc:
        _log.warning("platform_settings check skipped: %s", exc)

    # ── 1) لقطة الصحّة + البحث (بيانات حقيقية، مستقلّة عن الـ LLM) ──
    health: dict[str, Any] = {}
    health_html = ""
    try:
        from api.utils.platform_health import build_health_report, render_health_html
        health = build_health_report(weekly=weekly)
        health_html = render_health_html(health)
    except Exception as exc:
        _log.warning("health report failed: %s", exc)

    # ── 2) توجيهات الـ LLM — الأسبوعي فقط ──
    summary = ""
    directives_html = ""
    if weekly:
        try:
            result = generate_directive()
            if result.get("refused_by_guardian"):
                _log.warning("Weekly directives skipped — Financial Guardian refused")
            else:
                summary = (result.get("summary") or "").strip()
                directives_html = _render_directives_html(result)
        except Exception as exc:
            _log.exception("generate_directive crashed: %s", exc)

    # ── 3) موضوع الرسالة + الشارة ──
    severity = "warning" if _health_urgent(health) else "info"
    gsc = health.get("gsc") or {}
    users_total = (health.get("users") or {}).get("total", 0)

    if weekly:
        subject = "📈 التقرير الأسبوعي — " + (summary[:70] if summary else "ملخّص أداء المنصة")
    else:
        bits = []
        if gsc:
            bits.append(f"{gsc['clicks']:,} نقرة/٢٨ي")
        if users_total:
            bits.append(f"{users_total:,} مستخدم")
        subject = "📊 نبض الصفقات اليومي" + (f" — {' · '.join(bits)}" if bits else "")

    # ── 4) تجميع الجسم ──
    body_parts: list[str] = []
    if weekly and summary:
        body_parts.append(f"<p style='font-size:15px;margin:0 0 6px;'><b>الخلاصة:</b> {summary}</p>")
    if health_html:
        body_parts.append(health_html)
    if directives_html:
        body_parts.append(directives_html)
    if not health_html and not directives_html:
        body_parts.append("<p style='color:#6B7280;'>تعذّر بناء التقرير هذه الدورة — راجع سجلّ الخادم.</p>")
    body_parts.append(
        "<hr style='border:none;border-top:1px solid #E5E7EB;margin:18px 0 10px;'>"
        "<p style='color:#9CA3AF;font-size:11px;margin:0;'>"
        "تقرير آلي — نبض الصفقات · الضبط من صفحة «🛰️ متابعة المنصة» في الداشبورد.</p>"
    )

    try:
        send_ops_alert(subject=subject, body_html="".join(body_parts),
                       severity=severity, to=recipient)
        _log.info("%s digest emailed (severity=%s, weekly_directives=%s)",
                  mode, severity, bool(directives_html))
    except Exception as exc:
        _log.error("Failed to email %s digest: %s", mode, exc)
