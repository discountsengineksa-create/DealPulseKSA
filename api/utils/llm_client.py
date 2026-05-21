"""
Anthropic Claude client — single entry point for every LLM call in the platform.

Responsibilities:
  • Reads ANTHROPIC_API_KEY (and falls back to a clear error if missing)
  • Pre-flight integration with Financial Guardian (precharge → call → settle)
  • Per-call logging into llm_call_log
  • Cost estimation per model (per-token table kept in MODEL_PRICING)
  • Standard error handling (rate limits, retries, transient network)

Public API:
    call_claude(
        purpose: str,
        system: str,
        user: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        temperature: float = 0.4,
    ) -> CallResult
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from anthropic import Anthropic, APIError, RateLimitError  # type: ignore[import-untyped]

from api.db import get_db_context
from api.utils.financial_guardian import precharge, settle

_log = logging.getLogger("dp.llm")

DEFAULT_MODEL = "claude-sonnet-4-6"

# Anthropic pricing (USD per 1M tokens). Update when Anthropic updates rates.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_id              (input $/1M,   output $/1M)
    "claude-opus-4-7":      (15.00,        75.00),
    "claude-sonnet-4-6":    ( 3.00,        15.00),
    "claude-haiku-4-5":     ( 0.80,         4.00),
    # Older fallbacks if env still pins them
    "claude-3-5-sonnet":    ( 3.00,        15.00),
    "claude-3-5-haiku":     ( 0.80,         4.00),
}

_client: Optional[Anthropic] = None


def _get_client() -> Anthropic:
    global _client
    if _client is not None:
        return _client
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY غير معرّف. اضبطه في Railway env vars قبل التشغيل."
        )
    _client = Anthropic(api_key=key)
    return _client


def estimate_cost_usd(model: str, in_tokens: int, out_tokens: int) -> float:
    """Forecast cost based on price table. Used by Financial Guardian precharge."""
    in_price, out_price = MODEL_PRICING.get(model, MODEL_PRICING[DEFAULT_MODEL])
    return (in_tokens * in_price + out_tokens * out_price) / 1_000_000


@dataclass
class CallResult:
    text: str
    model: str
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_ms: int
    refused_by_guardian: bool = False


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


def call_claude(
    *,
    purpose: str,
    system: str,
    user: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
    temperature: float = 0.4,
    estimated_in_tokens: int | None = None,
) -> CallResult:
    """
    Single-shot Claude call with full guardian + audit trail.

    Workflow:
      1. Estimate cost (or use caller-provided estimate)
      2. Financial Guardian precharge — if denied, return refused result
      3. Anthropic API call (with one retry on RateLimitError)
      4. Settle actual vs estimated cost
      5. Log to llm_call_log
      6. Return CallResult

    Raises only on programming bugs (missing API key). All transport
    errors are caught and surfaced via CallResult with empty text.
    """
    # 1) Estimate
    est_in = estimated_in_tokens if estimated_in_tokens is not None else int(
        (len(system) + len(user)) / 3.5  # rough chars→tokens heuristic
    )
    est_out = max_tokens
    est_cost = estimate_cost_usd(model, est_in, est_out)

    # 2) Pre-charge through Financial Guardian
    if not precharge(est_cost, purpose=purpose):
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=0,
                  success=False, error="financial_guardian_refused")
        return CallResult(
            text="", model=model, tokens_input=0, tokens_output=0,
            cost_usd=0.0, latency_ms=0, refused_by_guardian=True,
        )

    client = _get_client()
    start = time.time()

    # 3) Anthropic call with one retry on rate limit
    last_err: Optional[Exception] = None
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            break
        except RateLimitError as exc:
            last_err = exc
            _log.warning("Claude rate-limited (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
        except APIError as exc:
            last_err = exc
            _log.error("Claude API error: %s", exc)
            break
        except Exception as exc:
            last_err = exc
            _log.error("Claude unexpected error: %s", exc)
            break
    else:
        # All retries exhausted
        pass

    latency_ms = int((time.time() - start) * 1000)

    if last_err is not None and "response" not in dir():
        # Settlement: nothing actually charged → refund estimated
        settle(actual_cost_usd=0.0, estimated_cost_usd=est_cost)
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=latency_ms,
                  success=False, error=str(last_err)[:500])
        return CallResult(text="", model=model, tokens_input=0, tokens_output=0,
                          cost_usd=0.0, latency_ms=latency_ms)

    # 4) Parse usage + actual cost
    in_tokens = response.usage.input_tokens
    out_tokens = response.usage.output_tokens
    actual_cost = estimate_cost_usd(model, in_tokens, out_tokens)

    settle(actual_cost_usd=actual_cost, estimated_cost_usd=est_cost)

    # 5) Extract text from the first content block
    text = ""
    if response.content and len(response.content) > 0:
        block = response.content[0]
        text = getattr(block, "text", "") or ""

    # 6) Audit
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
