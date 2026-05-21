"""
Google Gemini client — single entry point for every LLM call in the platform.

Why Gemini (vs Anthropic):
    Free tier provides 1500 req/day on flash models — enough for our
    every-3h directive cycle (8/day) + retries + manual triggers.
    Same Financial Guardian + semantic cache architecture, only the
    transport changes.

Public API:
    call_llm(
        purpose: str,
        system: str,
        user: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> CallResult

Backwards compat: also exposes `call_claude` as an alias so any caller
that imported the prior name keeps working without edits.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import google.generativeai as genai  # type: ignore[import-untyped]
from google.api_core import exceptions as google_exc  # type: ignore[import-untyped]

from api.db import get_db_context
from api.utils.financial_guardian import precharge, settle

_log = logging.getLogger("dp.llm")

# Default model: 2.0-flash = أكبر free quota + متاح في v1 الحالي.
# (gemini-1.5-* deprecated في v1beta — استخدم 2.x فقط.)
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ─────────────────────────────────────────────────────────────────────────────
# Pricing & Free-tier quotas
# ─────────────────────────────────────────────────────────────────────────────
# الأرقام بـ USD per 1M tokens — paid tier (لو تجاوزنا free quota).
# للـ free tier، الحدود rate-based (RPD/RPM) لا cost-based. نخزّن تكلفة
# "ظلّية" صغيرة لكل call عشان Financial Guardian يقدر يكون رؤية موحّدة
# لاستهلاكنا حتى وإن كانت الـ calls مجانية فعلياً.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_id                (input $/1M,   output $/1M)
    "gemini-2.5-flash":       (0.30,         2.50),
    "gemini-2.5-pro":         (1.25,        10.00),
    "gemini-2.0-flash":       (0.10,         0.40),
    "gemini-2.0-flash-lite":  (0.075,        0.30),
    "gemini-2.0-flash-001":   (0.10,         0.40),
    "gemini-2.0-flash-exp":   (0.10,         0.40),
}

# Daily request quotas للـ free tier (نتتبعها في Redis عشان نمنع 429 surprise).
FREE_DAILY_QUOTA: dict[str, int] = {
    "gemini-2.5-flash":       500,
    "gemini-2.5-pro":         50,
    "gemini-2.0-flash":       1500,
    "gemini-2.0-flash-lite":  1500,
    "gemini-2.0-flash-001":   1500,
    "gemini-2.0-flash-exp":   1500,
}

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY غير معرّف. اضبطه في Railway env vars قبل التشغيل "
            "(https://aistudio.google.com/app/apikey)."
        )
    genai.configure(api_key=key)
    _configured = True


def estimate_cost_usd(model: str, in_tokens: int, out_tokens: int) -> float:
    """Forecast cost based on price table. Used by Financial Guardian precharge."""
    in_price, out_price = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    return (in_tokens * in_price + out_tokens * out_price) / 1_000_000


# ─────────────────────────────────────────────────────────────────────────────
# Daily quota guard — مستقل عن Financial Guardian (cost-based)
# ─────────────────────────────────────────────────────────────────────────────
def _quota_key(model: str) -> str:
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"gemini:quota:{day}:{model}"


def _check_and_increment_quota(model: str) -> tuple[bool, int]:
    """
    Returns (allowed, current_count).
    Falls back to allowing the call if Redis is unreachable — better to
    risk a 429 from Google than to silently block all LLM traffic.
    """
    from api.utils.redis_client import get_redis
    limit = FREE_DAILY_QUOTA.get(model, 1500)
    try:
        r = get_redis()
        new_count = r.incrbyfloat(_quota_key(model), 1)
        r.expire(_quota_key(model), 60 * 60 * 36)  # 36h TTL safety margin
        cur = int(new_count)
        if cur > limit:
            # rollback
            r.incrbyfloat(_quota_key(model), -1)
            return False, cur - 1
        return True, cur
    except Exception as exc:
        _log.warning("Quota check failed (%s) — allowing call", exc)
        return True, -1


@dataclass
class CallResult:
    text: str
    model: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_ms: int
    refused_by_guardian: bool = False
    refused_by_quota: bool = False


def _log_call(
    *, purpose: str, model: str, cache_hit: bool, in_tokens: int, out_tokens: int,
    cost: float, latency_ms: int, success: bool, error: Optional[str] = None,
) -> None:
    """Persist an audit row to llm_call_log (best-effort — never raises)."""
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO llm_call_log
                        (purpose, model, cache_hit, tokens_input, tokens_output,
                         cost_usd, latency_ms, success, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (purpose, model, cache_hit, in_tokens, out_tokens,
                     cost, latency_ms, success, (error or "")[:1000] or None),
                )
    except Exception as exc:
        _log.warning("llm_call_log insert failed: %s", exc)


def call_llm(
    *,
    purpose: str,
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2048,
    temperature: float = 0.4,
    estimated_in_tokens: int | None = None,
) -> CallResult:
    """
    Single-shot Gemini call with quota + guardian + audit.

    Workflow:
      1. Estimate cost (or use caller-provided estimate)
      2. Daily quota check (rate-limit per model, free tier)
      3. Financial Guardian precharge (cost-based)
      4. Gemini API call (one retry on transient errors)
      5. Settle actual vs estimated cost
      6. Log to llm_call_log
      7. Return CallResult

    Any failure surfaces via CallResult.text == "" — never raises
    except for missing API key (config bug).
    """
    # 1) Estimate
    est_in = estimated_in_tokens if estimated_in_tokens is not None else int(
        (len(system) + len(user)) / 3.5  # rough chars→tokens heuristic
    )
    est_out = max_tokens
    est_cost = estimate_cost_usd(model, est_in, est_out)

    # 2) Daily quota gate
    allowed, cur_count = _check_and_increment_quota(model)
    if not allowed:
        limit = FREE_DAILY_QUOTA.get(model, 1500)
        _log.warning("Quota exceeded for %s: %d/%d", model, cur_count, limit)
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=0,
                  success=False, error=f"daily_quota_exhausted ({cur_count}/{limit})")
        return CallResult(text="", model=model, tokens_input=0, tokens_output=0,
                          cost_usd=0.0, latency_ms=0, refused_by_quota=True)

    # 3) Financial Guardian (cost-based — يحمي حتى لو طلعنا من free tier)
    if not precharge(est_cost, purpose=purpose):
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=0,
                  success=False, error="financial_guardian_refused")
        return CallResult(
            text="", model=model, tokens_input=0, tokens_output=0,
            cost_usd=0.0, latency_ms=0, refused_by_guardian=True,
        )

    _ensure_configured()
    start = time.time()
    response: Any = None
    last_err: Optional[Exception] = None

    # 4) Gemini call with one retry on transient/rate errors
    for attempt in range(2):
        try:
            gen_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                    "response_mime_type": "application/json",
                },
            )
            response = gen_model.generate_content(user)
            last_err = None
            break
        except google_exc.ResourceExhausted as exc:
            last_err = exc
            _log.warning("Gemini quota/rate-limited (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
        except google_exc.GoogleAPICallError as exc:
            last_err = exc
            _log.error("Gemini API error: %s", exc)
            break
        except Exception as exc:
            last_err = exc
            _log.error("Gemini unexpected error: %s", exc)
            break

    latency_ms = int((time.time() - start) * 1000)

    if response is None or last_err is not None:
        # Settlement: nothing actually charged → refund estimated
        settle(actual_cost_usd=0.0, estimated_cost_usd=est_cost)
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=latency_ms,
                  success=False, error=str(last_err)[:500] if last_err else "no_response")
        return CallResult(text="", model=model, tokens_input=0, tokens_output=0,
                          cost_usd=0.0, latency_ms=latency_ms)

    # 5) Parse usage + actual cost
    usage = getattr(response, "usage_metadata", None)
    in_tokens = int(getattr(usage, "prompt_token_count", 0)) if usage else 0
    out_tokens = int(getattr(usage, "candidates_token_count", 0)) if usage else 0
    actual_cost = estimate_cost_usd(model, in_tokens, out_tokens)

    settle(actual_cost_usd=actual_cost, estimated_cost_usd=est_cost)

    # 6) Extract text — Gemini concatenates parts
    text = ""
    try:
        text = response.text or ""
    except Exception:
        # Fallback: assemble manually if response.text raised (e.g., blocked content)
        try:
            text = "".join(
                part.text for cand in (response.candidates or [])
                for part in (cand.content.parts or []) if hasattr(part, "text")
            )
        except Exception:
            text = ""

    # 7) Audit
    _log_call(purpose=purpose, model=model, cache_hit=False,
              in_tokens=in_tokens, out_tokens=out_tokens,
              cost=actual_cost, latency_ms=latency_ms, success=True)

    return CallResult(
        text=text,
        model=model,
        tokens_input=in_tokens,
        tokens_output=out_tokens,
        cost_usd=actual_cost,
        latency_ms=latency_ms,
    )


# Backwards-compat alias — any module that still imports call_claude
# will get the new Gemini-backed implementation without code change.
call_claude = call_llm
