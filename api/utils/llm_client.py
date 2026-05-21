"""
OpenRouter LLM client — OpenAI-compatible router across many providers.

Why OpenRouter:
    Some regions (incl. KSA) get free_tier_requests limit=0 on Google's
    direct Gemini API. OpenRouter proxies the same models from its own
    inventory + free models from Llama/Phi/Gemma — bypassing regional
    restrictions with a uniform OpenAI-compatible API.

    Default model: google/gemini-2.0-flash-exp:free
    Free tier: ~50 req/day per :free model, 200 across all
    Paid models also available (very cheap, no provider lock-in).

Public API:
    call_llm(
        purpose: str,
        system: str,
        user: str,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> CallResult

Backwards compat: call_claude = call_llm alias preserved.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from openai import OpenAI  # type: ignore[import-untyped]
from openai import APIError, RateLimitError, APIConnectionError  # type: ignore[import-untyped]

from api.db import get_db_context
from api.utils.financial_guardian import precharge, settle

_log = logging.getLogger("dp.llm")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
APP_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://dealpulseksa.com")
APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "DealPulse KSA")

DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")

# ─────────────────────────────────────────────────────────────────────────────
# Pricing & Free-tier quotas
# ─────────────────────────────────────────────────────────────────────────────
# الأرقام بـ USD per 1M tokens — حسب OpenRouter rate card.
# الموديلات بـ :free لها cost=0 (لكن نخزن قيمة وهمية صغيرة عشان Guardian
# يحتفظ بسجل النشاط حتى وإن كانت الـ calls مجانية فعلياً).
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_id                                    (input $/1M, output $/1M)
    "google/gemini-2.0-flash-exp:free":           (0.0,        0.0),
    "google/gemini-2.0-flash-001":                (0.10,       0.40),
    "google/gemini-flash-1.5":                    (0.075,      0.30),
    "meta-llama/llama-3.3-70b-instruct:free":     (0.0,        0.0),
    "meta-llama/llama-3.3-70b-instruct":          (0.39,       0.39),
    "mistralai/mistral-7b-instruct:free":         (0.0,        0.0),
    "google/gemma-2-9b-it:free":                  (0.0,        0.0),
    "anthropic/claude-3.5-haiku":                 (0.80,       4.00),
    "anthropic/claude-3.5-sonnet":                (3.00,       15.00),
    "openai/gpt-4o-mini":                         (0.15,       0.60),
}

# Daily request quotas للنماذج المجانية (نتتبعها في Redis).
# OpenRouter limit الفعلي يختلف حسب الـ tier؛ نضع أرقام محافظة.
FREE_DAILY_QUOTA: dict[str, int] = {
    "google/gemini-2.0-flash-exp:free":           50,
    "meta-llama/llama-3.3-70b-instruct:free":     50,
    "mistralai/mistral-7b-instruct:free":         50,
    "google/gemma-2-9b-it:free":                  50,
}
DEFAULT_PAID_QUOTA = 10_000  # نقدّر سقف معقول لتجنب runaway calls

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is not None:
        return _client
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY غير معرّف. اضبطه في Railway env vars قبل التشغيل "
            "(https://openrouter.ai/keys)."
        )
    _client = OpenAI(
        api_key=key,
        base_url=OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": APP_REFERER,
            "X-Title": APP_TITLE,
        },
    )
    return _client


def estimate_cost_usd(model: str, in_tokens: int, out_tokens: int) -> float:
    """Forecast cost based on price table. Free models return 0."""
    in_price, out_price = MODEL_PRICING.get(model, MODEL_PRICING.get(DEFAULT_MODEL, (0.0, 0.0)))
    return (in_tokens * in_price + out_tokens * out_price) / 1_000_000


# ─────────────────────────────────────────────────────────────────────────────
# Daily quota guard
# ─────────────────────────────────────────────────────────────────────────────
def _quota_key(model: str) -> str:
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"openrouter:quota:{day}:{model}"


def _quota_limit(model: str) -> int:
    """Free models get their explicit daily quota; paid get a safety ceiling."""
    if model in FREE_DAILY_QUOTA:
        return FREE_DAILY_QUOTA[model]
    if model.endswith(":free"):
        return 50
    return DEFAULT_PAID_QUOTA


def _check_and_increment_quota(model: str) -> tuple[bool, int]:
    """
    Returns (allowed, current_count).
    Falls back to allowing the call if Redis is unreachable.
    """
    from api.utils.redis_client import get_redis
    limit = _quota_limit(model)
    try:
        r = get_redis()
        new_count = r.incrbyfloat(_quota_key(model), 1)
        r.expire(_quota_key(model), 60 * 60 * 36)
        cur = int(new_count)
        if cur > limit:
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
    Single-shot OpenRouter call with quota + guardian + audit.

    Workflow:
      1. Estimate cost (or use caller-provided estimate)
      2. Daily quota check (per model, free or paid)
      3. Financial Guardian precharge (cost-based)
      4. OpenRouter API call via openai SDK
      5. Settle actual cost
      6. Log to llm_call_log
      7. Return CallResult
    """
    # 1) Estimate
    est_in = estimated_in_tokens if estimated_in_tokens is not None else int(
        (len(system) + len(user)) / 3.5
    )
    est_out = max_tokens
    est_cost = estimate_cost_usd(model, est_in, est_out)

    # 2) Daily quota gate
    allowed, cur_count = _check_and_increment_quota(model)
    if not allowed:
        limit = _quota_limit(model)
        _log.warning("Quota exceeded for %s: %d/%d", model, cur_count, limit)
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=0,
                  success=False, error=f"daily_quota_exhausted ({cur_count}/{limit})")
        return CallResult(text="", model=model, tokens_input=0, tokens_output=0,
                          cost_usd=0.0, latency_ms=0, refused_by_quota=True)

    # 3) Financial Guardian
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
    response: Any = None
    last_err: Optional[Exception] = None

    # 4) OpenRouter call with one retry on transient/rate errors
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},  # force JSON output
            )
            last_err = None
            break
        except RateLimitError as exc:
            last_err = exc
            _log.warning("OpenRouter rate-limited (attempt %d): %s", attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
        except (APIError, APIConnectionError) as exc:
            last_err = exc
            _log.error("OpenRouter API error: %s", exc)
            break
        except Exception as exc:
            last_err = exc
            _log.error("OpenRouter unexpected error: %s", exc)
            break

    latency_ms = int((time.time() - start) * 1000)

    if response is None or last_err is not None:
        settle(actual_cost_usd=0.0, estimated_cost_usd=est_cost)
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=latency_ms,
                  success=False, error=str(last_err)[:500] if last_err else "no_response")
        return CallResult(text="", model=model, tokens_input=0, tokens_output=0,
                          cost_usd=0.0, latency_ms=latency_ms)

    # 5) Parse usage + cost
    usage = getattr(response, "usage", None)
    in_tokens = int(getattr(usage, "prompt_tokens", 0)) if usage else 0
    out_tokens = int(getattr(usage, "completion_tokens", 0)) if usage else 0
    actual_cost = estimate_cost_usd(model, in_tokens, out_tokens)

    settle(actual_cost_usd=actual_cost, estimated_cost_usd=est_cost)

    # 6) Extract text from the first choice
    text = ""
    try:
        text = response.choices[0].message.content or ""
    except (AttributeError, IndexError):
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


# Backwards-compat alias
call_claude = call_llm
