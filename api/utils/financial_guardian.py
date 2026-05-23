"""
Daily LLM spend counter, backed by Redis.

Every call that intends to spend LLM tokens MUST go through `precharge()`
first. When the daily cap is hit, precharge() returns False and the caller
MUST short-circuit (e.g., enqueue to a `held` queue or return cached output).

Single atomic counter per UTC day:
    KEY  =  llm:spend:cents:YYYY-MM-DD
    TTL  =  48h (safety margin past midnight rollover)

A single threshold-breach email fires the first time we cross
DAILY_LLM_BUDGET_USD * SOFT_THRESHOLD (default 80%). Idempotency is enforced
via a sentinel key `llm:alert:sent:YYYY-MM-DD`.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from .redis_client import get_redis

_log = logging.getLogger("dp.guardian")

DEFAULT_DAILY_CAP_USD = float(os.getenv("DAILY_LLM_BUDGET_USD", "5.00"))
SOFT_THRESHOLD = float(os.getenv("DAILY_LLM_SOFT_THRESHOLD", "0.80"))
TTL_SECONDS = 60 * 60 * 48


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _spend_key() -> str:
    return f"llm:spend:cents:{_today_key()}"


def _alert_key() -> str:
    return f"llm:alert:sent:{_today_key()}"


def current_spend_usd() -> float:
    """Return today's spend so far in USD."""
    raw = get_redis().get(_spend_key())
    cents = float(raw) if raw else 0.0
    return cents / 100.0


def cap_usd() -> float:
    """Return the configured daily cap in USD."""
    return DEFAULT_DAILY_CAP_USD


def precharge(estimated_cost_usd: float, *, purpose: str) -> bool:
    """
    Reserve spend BEFORE calling the LLM.

    Returns True if we're still under cap (and the spend is recorded).
    Returns False if the call would breach the cap — caller MUST abort.

    Atomic INCRBYFLOAT means concurrent callers cannot race past the cap.
    """
    if estimated_cost_usd < 0:
        return True

    r = get_redis()
    key = _spend_key()
    cents = int(round(estimated_cost_usd * 100))

    # Atomic add — even if multiple workers call simultaneously, the totals
    # are correct. Redis returns the new total.
    new_total_cents = r.incrbyfloat(key, cents)
    r.expire(key, TTL_SECONDS)

    new_total_usd = float(new_total_cents) / 100.0
    cap = cap_usd()

    _log.info("LLM precharge: +$%.4f (%s) → today total: $%.4f / $%.2f",
              estimated_cost_usd, purpose, new_total_usd, cap)

    if new_total_usd > cap:
        # Refund the precharge so reported spend stays accurate.
        r.incrbyfloat(key, -cents)
        _log.warning("LLM cap exceeded — refusing %s (would total $%.4f > $%.2f)",
                     purpose, new_total_usd, cap)
        _maybe_send_cap_breach_email(new_total_usd, cap, purpose)
        return False

    # Soft-threshold notification (fires at most once per day).
    if new_total_usd >= cap * SOFT_THRESHOLD and not r.get(_alert_key()):
        _send_soft_threshold_email(new_total_usd, cap, purpose)
        r.set(_alert_key(), "1")
        r.expire(_alert_key(), TTL_SECONDS)

    return True


def settle(actual_cost_usd: float, estimated_cost_usd: float) -> None:
    """
    Reconcile actual vs estimated cost. Call after the LLM responds with
    usage data. Positive delta = we under-precharged; negative = we
    over-precharged. The counter is updated either way.
    """
    delta = actual_cost_usd - estimated_cost_usd
    if abs(delta) < 0.0001:
        return
    r = get_redis()
    r.incrbyfloat(_spend_key(), int(round(delta * 100)))
    r.expire(_spend_key(), TTL_SECONDS)


# ─── Internal notification helpers ──────────────────────────────────────────

def _send_soft_threshold_email(total: float, cap: float, purpose: str) -> None:
    try:
        from .email_alerts import send_ops_alert
        send_ops_alert(
            subject=f"⚠️ LLM spend at {int(SOFT_THRESHOLD * 100)}% of daily cap",
            body_html=(
                f"<p>Today's LLM spend has reached <b>${total:.2f}</b> "
                f"of the <b>${cap:.2f}</b> daily cap.</p>"
                f"<p>Latest call: <code>{purpose}</code></p>"
                f"<p>The Financial Guardian will refuse new precharges once "
                f"the cap is hit. Review recent activity in <code>ai_directives</code> "
                f"and <code>llm_semantic_cache</code>.</p>"
            ),
            severity="warning",
        )
    except Exception as exc:
        _log.error("Failed to send soft-threshold alert: %s", exc)


def _maybe_send_cap_breach_email(would_be_total: float, cap: float, purpose: str) -> None:
    """One critical email the first time we *refuse* a call."""
    r = get_redis()
    sentinel = f"llm:alert:breach:{_today_key()}"
    if r.get(sentinel):
        return
    try:
        from .email_alerts import send_ops_alert
        send_ops_alert(
            subject="🚨 LLM daily cap reached — calls now refused",
            body_html=(
                f"<p>A precharge for <code>{purpose}</code> would have pushed "
                f"today's spend to <b>${would_be_total:.2f}</b> — over the "
                f"<b>${cap:.2f}</b> daily cap.</p>"
                f"<p>The Financial Guardian is now refusing all LLM calls "
                f"until 00:00 UTC. Held jobs will retry tomorrow.</p>"
                f"<p>To raise the cap manually, set "
                f"<code>DAILY_LLM_BUDGET_USD</code> in Railway env vars.</p>"
            ),
            severity="critical",
        )
        r.set(sentinel, "1")
        r.expire(sentinel, TTL_SECONDS)
    except Exception as exc:
        _log.error("Failed to send cap-breach alert: %s", exc)
