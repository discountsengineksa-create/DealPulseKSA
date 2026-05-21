"""
Directive generator worker — invoked by APScheduler every 3 hours.

Flow:
  1. generate_directive() builds snapshot, hits cache or calls Gemini,
     persists to ai_directives, returns dict.
  2. If a real (non-refused) directive came back, send a summary email
     to the ops team via send_ops_alert.

Failures are logged but never raised — the scheduler keeps the worker
healthy regardless of LLM availability.
"""
from __future__ import annotations

import logging
from typing import Any

from api.utils.email_alerts import send_ops_alert
from api.utils.llm_service import generate_directive

_log = logging.getLogger("dp.directive")


def _render_email_html(result: dict[str, Any]) -> str:
    """Render the directive dict as an Arabic HTML email body."""
    directives = result.get("directives") or []
    summary = result.get("summary", "")
    cache_hit = result.get("cache_hit", False)
    model = result.get("model", "")
    cost = result.get("cost_usd", 0.0)
    in_tok = result.get("tokens_input", 0)
    out_tok = result.get("tokens_output", 0)

    parts = [f"<p><b>الملخّص:</b> {summary}</p>"] if summary else []

    if directives:
        parts.append("<h3 style='color:#059669;margin:18px 0 10px;'>التوجيهات التشغيلية</h3>")
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
    else:
        parts.append("<p style='color:#6B7280;'>لا توجد توجيهات حالياً.</p>")

    parts.append(
        f"<hr style='border:none;border-top:1px solid #E5E7EB;margin:18px 0;'>"
        f"<p style='color:#6B7280;font-size:12px;'>"
        f"النموذج: <code>{model}</code> · "
        f"{'cache HIT' if cache_hit else 'cache MISS'} · "
        f"tokens: in={in_tok}, out={out_tok} · "
        f"تكلفة: ${cost:.5f}</p>"
    )
    return "".join(parts)


def run_directive_cycle() -> None:
    """One cycle: generate directive + email summary. Idempotent on cache hit."""
    try:
        result = generate_directive()
    except Exception as exc:
        _log.exception("generate_directive crashed: %s", exc)
        return

    if result.get("refused_by_guardian"):
        _log.warning("Skipping email — Financial Guardian refused this cycle")
        return

    summary = result.get("summary") or "تحديث AI ذكي"
    severity = "info" if result.get("cache_hit") else "warning"

    subject = f"🧠 توجيهات AI — {summary[:80]}"
    body_html = _render_email_html(result)

    try:
        send_ops_alert(subject=subject, body_html=body_html, severity=severity)
        _log.info("Directive %s emailed (cache_hit=%s, cost=$%.5f)",
                  result.get("directive_id"), result.get("cache_hit"),
                  result.get("cost_usd", 0.0))
    except Exception as exc:
        _log.error("Failed to email directive %s: %s", result.get("directive_id"), exc)
