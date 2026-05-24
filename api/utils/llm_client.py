"""
LLM client with Gemini (primary) → OpenRouter (fallback) failover.

Why failover:
    Direct Gemini API is faster, cheaper (per-token), and has prompt
    caching native to the SDK. But some regions (incl. KSA) get a
    free-tier limit of 0 and require billing. OpenRouter proxies the
    same models without regional restrictions and has a generous free
    pool, but its free models are bursty and rate-limited upstream.

    Solution: try Gemini first. If it returns 404/429/quota errors or
    times out, transparently retry through OpenRouter. The caller
    receives a CallResult with a `provider` field indicating which
    backend actually answered, and `fallback_used=True` when we had
    to switch.

Public API:
    call_llm(
        purpose: str,
        system: str,
        user: str,
        model: str | None = None,        # let backend pick its default
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

# Both SDKs are optional — the missing one just disables that backend
try:
    import google.generativeai as genai  # type: ignore[import-untyped]
    from google.api_core import exceptions as google_exc  # type: ignore[import-untyped]
    _GEMINI_SDK_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore[assignment]
    google_exc = None  # type: ignore[assignment]
    _GEMINI_SDK_AVAILABLE = False

try:
    from openai import OpenAI  # type: ignore[import-untyped]
    from openai import APIError, RateLimitError, APIConnectionError  # type: ignore[import-untyped]
    _OPENAI_SDK_AVAILABLE = True
except ImportError:
    OpenAI = None  # type: ignore[assignment]
    APIError = RateLimitError = APIConnectionError = Exception  # type: ignore[misc,assignment]
    _OPENAI_SDK_AVAILABLE = False

from api.db import get_db_context
from api.utils.financial_guardian import precharge, settle

_log = logging.getLogger("dp.llm")

# ─────────────────────────────────────────────────────────────────────────────
# Provider configuration
# ─────────────────────────────────────────────────────────────────────────────
GEMINI_DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
OPENROUTER_DEFAULT_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
DEFAULT_MODEL = GEMINI_DEFAULT_MODEL  # kept for callers that ask "what's the default?"


def _build_openrouter_chain() -> list[str]:
    """
    سلسلة موديلات OpenRouter للتجربة بالتتابع — لو موديل مات (404 No endpoints)
    أو امتلأت حصته، ننتقل للتالي تلقائياً. يمنع تكرار توقّف الـ LLM كلما اختفى
    موديل مجاني (المجانيات تتغيّر باستمرار).

    التخصيص: OPENROUTER_MODELS="a,b,c" (مفصولة بفواصل) يلغي السلسلة الافتراضية،
    أو OPENROUTER_MODEL=x يضع x في المقدّمة.
    """
    raw = os.getenv("OPENROUTER_MODELS", "")
    chain = [m.strip() for m in raw.split(",") if m.strip()]
    if not chain:
        # تحديث 2026-05: gemma-2-9b-it:free تم سحبه من OpenRouter (404).
        # أضفنا DeepSeek في المقدّمة لأنه الأكثر استقراراً مجاناً.
        chain = [
            OPENROUTER_DEFAULT_MODEL,
            "deepseek/deepseek-chat-v3-0324:free",       # موثوق + رخيص
            "deepseek/deepseek-r1:free",                  # احتياط ثاني موثوق
            "meta-llama/llama-3.3-70b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "mistralai/mistral-small-24b-instruct-2501:free",
            # محذوف: google/gemma-2-9b-it:free (404 No endpoints found)
        ]
    seen: set[str] = set()
    out: list[str] = []
    for m in chain:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


OPENROUTER_MODEL_CHAIN = _build_openrouter_chain()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_REFERER = os.getenv("OPENROUTER_HTTP_REFERER", "https://dealpulseksa.com")
OPENROUTER_APP_TITLE = os.getenv("OPENROUTER_APP_TITLE", "DealPulse KSA")

# Groq — مزوّد مجاني سريع وموثوق (OpenAI-compatible). مفتاح مجاني من
# console.groq.com. يُجرَّب بعد Gemini وقبل OpenRouter لأنه الأثبت مجاناً.
GROQ_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Pricing (USD per 1M tokens). Used by Financial Guardian to track spend
# across providers in a unified currency.
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # ── Google direct ──
    "gemini-2.5-flash":                            (0.30,         2.50),
    "gemini-2.5-pro":                              (1.25,        10.00),
    "gemini-2.0-flash":                            (0.10,         0.40),
    "gemini-2.0-flash-lite":                       (0.075,        0.30),
    "gemini-2.0-flash-001":                        (0.10,         0.40),
    # ── Groq (free tier) ──
    "llama-3.3-70b-versatile":                     (0.0,          0.0),
    "llama-3.1-8b-instant":                        (0.0,          0.0),
    # ── OpenRouter free pool ──
    "google/gemini-2.0-flash-exp:free":            (0.0,          0.0),
    "meta-llama/llama-3.3-70b-instruct:free":      (0.0,          0.0),
    "mistralai/mistral-small-24b-instruct-2501:free": (0.0,       0.0),
    "google/gemma-2-9b-it:free":                   (0.0,          0.0),
    "deepseek/deepseek-chat-v3-0324:free":         (0.0,          0.0),
    "deepseek/deepseek-r1:free":                   (0.0,          0.0),
    "qwen/qwen-2.5-72b-instruct:free":             (0.0,          0.0),
    # ── OpenRouter paid (failover safety) ──
    "google/gemini-2.0-flash-001":                 (0.10,         0.40),
    "anthropic/claude-3.5-haiku":                  (0.80,         4.00),
    "openai/gpt-4o-mini":                          (0.15,         0.60),
}

# Daily quotas — Redis-tracked rate gate, not cost gate
FREE_DAILY_QUOTA: dict[str, int] = {
    "llama-3.3-70b-versatile":                     1000,
    "llama-3.1-8b-instant":                        1000,
    "gemini-2.5-flash":                            500,
    "gemini-2.5-pro":                              50,
    "gemini-2.0-flash":                            1500,
    "gemini-2.0-flash-lite":                       1500,
    "gemini-2.0-flash-001":                        1500,
    "google/gemini-2.0-flash-exp:free":            50,
    "meta-llama/llama-3.3-70b-instruct:free":      50,
    "mistralai/mistral-small-24b-instruct-2501:free": 50,
    "google/gemma-2-9b-it:free":                   50,
    "deepseek/deepseek-chat-v3-0324:free":         50,
    "deepseek/deepseek-r1:free":                   50,
    "qwen/qwen-2.5-72b-instruct:free":             50,
}
DEFAULT_PAID_QUOTA = 10_000


@dataclass
class CallResult:
    text: str
    model: str
    provider: str = "unknown"        # 'gemini' | 'openrouter' | 'none'
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    refused_by_guardian: bool = False
    refused_by_quota: bool = False
    fallback_used: bool = False      # True when the primary failed and we switched
    error: Optional[str] = None      # last error message, if any


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def estimate_cost_usd(model: str, in_tokens: int, out_tokens: int) -> float:
    in_price, out_price = MODEL_PRICING.get(model, (0.0, 0.0))
    return (in_tokens * in_price + out_tokens * out_price) / 1_000_000


def _quota_key(provider: str, model: str) -> str:
    from datetime import datetime, timezone
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"{provider}:quota:{day}:{model}"


def _quota_limit(model: str) -> int:
    if model in FREE_DAILY_QUOTA:
        return FREE_DAILY_QUOTA[model]
    if model.endswith(":free"):
        return 50
    return DEFAULT_PAID_QUOTA


def _check_and_increment_quota(provider: str, model: str) -> tuple[bool, int]:
    from api.utils.redis_client import get_redis
    limit = _quota_limit(model)
    try:
        r = get_redis()
        new_count = r.incrbyfloat(_quota_key(provider, model), 1)
        r.expire(_quota_key(provider, model), 60 * 60 * 36)
        cur = int(new_count)
        if cur > limit:
            r.incrbyfloat(_quota_key(provider, model), -1)
            return False, cur - 1
        return True, cur
    except Exception as exc:
        _log.warning("Quota check failed (%s) — allowing call", exc)
        return True, -1


def _log_call(
    *, purpose: str, model: str, cache_hit: bool, in_tokens: int, out_tokens: int,
    cost: float, latency_ms: int, success: bool, error: Optional[str] = None,
) -> None:
    """Best-effort persist of one call row. Never raises."""
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


# ─────────────────────────────────────────────────────────────────────────────
# Gemini backend (primary)
# ─────────────────────────────────────────────────────────────────────────────
_gemini_configured = False


def _ensure_gemini_configured() -> bool:
    """Returns True if Gemini is usable. False if SDK or API key missing."""
    global _gemini_configured
    if _gemini_configured:
        return True
    if not _GEMINI_SDK_AVAILABLE:
        return False
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return False
    genai.configure(api_key=key)
    _gemini_configured = True
    return True


def _call_gemini(
    *, purpose: str, system: str, user: str, model: str,
    max_tokens: int, temperature: float, est_cost: float,
) -> CallResult:
    """One attempt against Gemini direct. Returns CallResult with error on failure."""
    start = time.time()
    response: Any = None
    last_err: Optional[Exception] = None

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
        settle(actual_cost_usd=0.0, estimated_cost_usd=est_cost)
        err_str = str(last_err)[:500] if last_err else "no_response"
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=latency_ms,
                  success=False, error=err_str)
        return CallResult(text="", model=model, provider="gemini",
                          latency_ms=latency_ms, error=err_str)

    usage = getattr(response, "usage_metadata", None)
    in_tokens = int(getattr(usage, "prompt_token_count", 0)) if usage else 0
    out_tokens = int(getattr(usage, "candidates_token_count", 0)) if usage else 0
    actual_cost = estimate_cost_usd(model, in_tokens, out_tokens)
    settle(actual_cost_usd=actual_cost, estimated_cost_usd=est_cost)

    text = ""
    try:
        text = response.text or ""
    except Exception:
        try:
            text = "".join(
                part.text for cand in (response.candidates or [])
                for part in (cand.content.parts or []) if hasattr(part, "text")
            )
        except Exception:
            text = ""

    _log_call(purpose=purpose, model=model, cache_hit=False,
              in_tokens=in_tokens, out_tokens=out_tokens,
              cost=actual_cost, latency_ms=latency_ms, success=True)

    return CallResult(
        text=text, model=model, provider="gemini",
        tokens_input=in_tokens, tokens_output=out_tokens,
        cost_usd=actual_cost, latency_ms=latency_ms,
    )


# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter backend (fallback)
# ─────────────────────────────────────────────────────────────────────────────
_openrouter_client: Optional[Any] = None


def _ensure_openrouter_client() -> bool:
    """Returns True if OpenRouter is usable."""
    global _openrouter_client
    if _openrouter_client is not None:
        return True
    if not _OPENAI_SDK_AVAILABLE:
        return False
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return False
    _openrouter_client = OpenAI(
        api_key=key,
        base_url=OPENROUTER_BASE_URL,
        timeout=60.0,                       # was 600s default — fail fast
        max_retries=0,                      # we have our own retry loop
        default_headers={
            "HTTP-Referer": OPENROUTER_REFERER,
            "X-Title": OPENROUTER_APP_TITLE,
        },
    )
    return True


def _call_openai_compatible(
    *, client: Any, provider: str, purpose: str, system: str, user: str, model: str,
    max_tokens: int, temperature: float, est_cost: float,
) -> CallResult:
    """محاولة واحدة على أي مزوّد OpenAI-compatible (OpenRouter / Groq / غيره)."""
    start = time.time()
    response: Any = None
    last_err: Optional[Exception] = None

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
            )
            last_err = None
            break
        except RateLimitError as exc:
            last_err = exc
            _log.warning("%s rate-limited (attempt %d): %s", provider, attempt + 1, exc)
            time.sleep(2 * (attempt + 1))
        except (APIError, APIConnectionError) as exc:
            last_err = exc
            _log.error("%s API error: %s", provider, exc)
            break
        except Exception as exc:
            last_err = exc
            _log.error("%s unexpected error: %s", provider, exc)
            break

    latency_ms = int((time.time() - start) * 1000)

    if response is None or last_err is not None:
        settle(actual_cost_usd=0.0, estimated_cost_usd=est_cost)
        err_str = str(last_err)[:500] if last_err else "no_response"
        _log_call(purpose=purpose, model=model, cache_hit=False,
                  in_tokens=0, out_tokens=0, cost=0, latency_ms=latency_ms,
                  success=False, error=err_str)
        return CallResult(text="", model=model, provider=provider,
                          latency_ms=latency_ms, error=err_str)

    usage = getattr(response, "usage", None)
    in_tokens = int(getattr(usage, "prompt_tokens", 0)) if usage else 0
    out_tokens = int(getattr(usage, "completion_tokens", 0)) if usage else 0
    actual_cost = estimate_cost_usd(model, in_tokens, out_tokens)
    settle(actual_cost_usd=actual_cost, estimated_cost_usd=est_cost)

    text = ""
    try:
        text = response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        text = ""

    _log_call(purpose=purpose, model=model, cache_hit=False,
              in_tokens=in_tokens, out_tokens=out_tokens,
              cost=actual_cost, latency_ms=latency_ms, success=True)

    return CallResult(
        text=text, model=model, provider=provider,
        tokens_input=in_tokens, tokens_output=out_tokens,
        cost_usd=actual_cost, latency_ms=latency_ms,
    )


def _call_openrouter(
    *, purpose: str, system: str, user: str, model: str,
    max_tokens: int, temperature: float, est_cost: float,
) -> CallResult:
    return _call_openai_compatible(
        client=_openrouter_client, provider="openrouter", purpose=purpose,
        system=system, user=user, model=model, max_tokens=max_tokens,
        temperature=temperature, est_cost=est_cost,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Groq backend (free, fast, reliable — recommended primary fallback)
# ─────────────────────────────────────────────────────────────────────────────
_groq_client: Optional[Any] = None


def _ensure_groq_client() -> bool:
    """Returns True if Groq is usable (GROQ_API_KEY set + SDK present)."""
    global _groq_client
    if _groq_client is not None:
        return True
    if not _OPENAI_SDK_AVAILABLE:
        return False
    key = os.getenv("GROQ_API_KEY")
    if not key:
        return False
    _groq_client = OpenAI(api_key=key, base_url=GROQ_BASE_URL, timeout=60.0, max_retries=0)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Public orchestrator — Gemini → OpenRouter failover
# ─────────────────────────────────────────────────────────────────────────────

def call_llm(
    *,
    purpose: str,
    system: str,
    user: str,
    model: Optional[str] = None,
    max_tokens: int = 2048,
    temperature: float = 0.4,
    estimated_in_tokens: int | None = None,
) -> CallResult:
    """
    Orchestrated call with automatic failover.

    Workflow:
      1. Try Gemini (if SDK + GEMINI_API_KEY available, quota OK,
         Financial Guardian allows).
      2. On Gemini failure (any reason — 404, 429, network, parse),
         fall back to OpenRouter (same checks repeat for the secondary).
      3. Return the first successful CallResult, with `fallback_used`
         flag set if we had to switch.

    If both providers fail, returns a CallResult with text="" and
    `error` populated for the final attempt.
    """
    # Shared cost estimate (heuristic) — used for both backends
    est_in = estimated_in_tokens if estimated_in_tokens is not None else int(
        (len(system) + len(user)) / 3.5
    )
    est_out = max_tokens

    # ─── Attempt 1: Gemini (primary) ───
    if _ensure_gemini_configured():
        primary_model = model or GEMINI_DEFAULT_MODEL
        # Pre-flight quota + budget gate
        allowed, _ = _check_and_increment_quota("gemini", primary_model)
        if not allowed:
            _log.warning("Gemini quota exhausted — going straight to OpenRouter")
        else:
            est_cost = estimate_cost_usd(primary_model, est_in, est_out)
            if not precharge(est_cost, purpose=purpose):
                _log_call(purpose=purpose, model=primary_model, cache_hit=False,
                          in_tokens=0, out_tokens=0, cost=0, latency_ms=0,
                          success=False, error="financial_guardian_refused")
                return CallResult(
                    text="", model=primary_model, provider="gemini",
                    refused_by_guardian=True,
                )

            result = _call_gemini(
                purpose=purpose, system=system, user=user, model=primary_model,
                max_tokens=max_tokens, temperature=temperature, est_cost=est_cost,
            )
            if result.text:
                _log.info("✅ Gemini answered (%s, %dms, $%.5f)",
                          primary_model, result.latency_ms, result.cost_usd)
                return result
            _log.warning("⚠️  Gemini failed → trying Groq/OpenRouter. Error: %s",
                         result.error)

    # ─── Attempt 1.5: Groq (مجاني، سريع، الأثبت) ───
    if _ensure_groq_client():
        gmodel = GROQ_DEFAULT_MODEL
        allowed, _ = _check_and_increment_quota("groq", gmodel)
        if allowed:
            est_cost = estimate_cost_usd(gmodel, est_in, est_out)  # = 0 (free)
            if precharge(est_cost, purpose=purpose):
                result = _call_openai_compatible(
                    client=_groq_client, provider="groq", purpose=purpose,
                    system=system, user=user, model=gmodel,
                    max_tokens=max_tokens, temperature=temperature, est_cost=est_cost,
                )
                result.fallback_used = True
                if result.text:
                    _log.info("✅ Groq answered (%s, %dms)", gmodel, result.latency_ms)
                    return result
                _log.warning("⚠️  Groq failed → trying OpenRouter. Error: %s", result.error)

    # ─── Attempt 2: OpenRouter (fallback chain) ───
    if not _ensure_openrouter_client():
        _log.error("No LLM backend answered (Gemini/Groq/OpenRouter all unavailable)")
        return CallResult(
            text="", model=model or "unknown", provider="none",
            error="no_provider_configured",
        )

    # نجرّب موديلات OpenRouter بالتتابع — موديل ميت/ممتلئ → التالي تلقائياً
    last_result: Optional[CallResult] = None
    for or_model in OPENROUTER_MODEL_CHAIN:
        allowed, _ = _check_and_increment_quota("openrouter", or_model)
        if not allowed:
            _log.warning("OpenRouter quota exhausted for %s — trying next model", or_model)
            continue

        est_cost = estimate_cost_usd(or_model, est_in, est_out)
        if not precharge(est_cost, purpose=purpose):
            # الحارس المالي رفض — السقف اليومي تخطّى، لا فائدة من موديل آخر
            _log_call(purpose=purpose, model=or_model, cache_hit=False,
                      in_tokens=0, out_tokens=0, cost=0, latency_ms=0,
                      success=False, error="financial_guardian_refused")
            return CallResult(text="", model=or_model, provider="openrouter",
                              refused_by_guardian=True, fallback_used=True)

        result = _call_openrouter(
            purpose=purpose, system=system, user=user, model=or_model,
            max_tokens=max_tokens, temperature=temperature, est_cost=est_cost,
        )
        result.fallback_used = True
        last_result = result
        if result.text:
            _log.info("✅ OpenRouter fallback answered (%s, %dms, $%.5f)",
                      or_model, result.latency_ms, result.cost_usd)
            return result
        _log.warning("⚠️  OpenRouter model %s failed (%s) — trying next",
                     or_model, (result.error or "")[:80])

    if last_result is not None:
        _log.error("❌ All OpenRouter models failed. Last error: %s", last_result.error)
        return last_result
    return CallResult(text="", model="none", provider="openrouter", fallback_used=True,
                      error="all_openrouter_models_exhausted_or_quota")


# Backwards-compat alias
call_claude = call_llm
