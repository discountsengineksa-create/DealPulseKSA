"""
LLM Directive Service — orchestrates the full directive lifecycle:

  1. Build a canonical input snapshot from the platform state (velocity
     matview + master expirations + per-category aggregates).
  2. Render a deterministic prompt (same input → same hash).
  3. Check llm_semantic_cache for an exact-hash hit.
  4. On miss: call Gemini via llm_client.call_llm (which itself goes
     through Financial Guardian + logs to llm_call_log).
  5. Persist to ai_directives + llm_semantic_cache.
  6. Return a dict the caller can email / surface in the dashboard.

This module is callable from:
  • api/workers/directive_generator.py     (every 3h scheduled)
  • api/routers/admin.py                   (manual /admin/trigger-directive)
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from psycopg2.extras import Json, RealDictCursor

from api.db import get_db_context
from api.utils.llm_client import call_llm

_log = logging.getLogger("dp.llm.service")

PURPOSE = "directive"
CACHE_TTL_HOURS = 6                  # توجيه ينتهي صلاحياً بعد 6 ساعات
DEFAULT_HORIZON_HOURS = 168          # توقّع الأسبوع القادم

# System prompt — يبقى ثابت بين كل استدعاءات؛ التغيير في user message
SYSTEM_PROMPT_AR = """أنت محلل أعمال محترف لمنصة DealPulse KSA — منصة كوبونات الخصم
في السعودية. مهمّتك تحليل بيانات الأداء آخر 48 ساعة وتوليد توجيهات تشغيلية
عملية ومحددة بلهجة بسيطة وواضحة.

قواعد:
1. اعطِ توجيهات قابلة للتنفيذ خلال الـ 7 أيام القادمة فقط.
2. كل توجيه يجب أن يذكر متجراً أو قسماً محدداً بالاسم (لا توصيات عامة).
3. ركّز على فرص الإيرادات: تجديد كوبونات، توسيع متاجر صاعدة، إيقاف خاسرة.
4. اكتب بنبرة استشارية مهنية — لا تستخدم emojis كثيرة.
5. ابدأ كل توجيه بفعل أمر واضح (مثل: "جدّد"، "وسّع"، "علّق"، "افحص").

أعد ردك كـ JSON صالح بهذا الشكل بالضبط:
{
  "summary": "ملخص في سطر واحد لأهم توصية (للـ subject line)",
  "directives": [
    {
      "priority": "high|medium|low",
      "action": "نص التوجيه بالعربي",
      "affected_master_ids": [1, 2, 3],
      "rationale": "سبب مختصر من البيانات"
    }
  ],
  "confidence": 0.75
}"""


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot builder
# ─────────────────────────────────────────────────────────────────────────────

def build_input_snapshot() -> dict[str, Any]:
    """جمع كل البيانات الإجمالية التي يحتاجها الـ LLM. مخرَج deterministic."""
    snapshot: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "horizon_hours": DEFAULT_HORIZON_HOURS,
        "window_hours": 48,
    }

    with get_db_context() as conn:
        # 1) أفضل 20 متجر من ناحية الـ 48h velocity
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    m.id            AS master_id,
                    m.store_id,
                    m.name_en,
                    COALESCE(m.store_tags, '{}')        AS tags_ar,
                    COALESCE(m.store_tags_en, '{}')     AS tags_en,
                    m.is_trending,
                    m.last_time,
                    m.discount_value,
                    m.public_coupon,
                    COALESCE(v.recent_1h, 0)            AS recent_1h,
                    COALESCE(v.recent_6h, 0)            AS recent_6h,
                    COALESCE(v.recent_48h, 0)           AS recent_48h,
                    COALESCE(v.hourly_mean, 0)          AS hourly_mean,
                    COALESCE(v.hourly_stddev, 0)        AS hourly_stddev
                FROM master m
                LEFT JOIN mv_store_velocity_48h v ON v.master_id = m.id
                ORDER BY COALESCE(v.recent_48h, 0) DESC
                LIMIT 20
            """)
            rows = cur.fetchall()
            snapshot["top_stores_48h"] = [
                {
                    "master_id": r["master_id"],
                    "store": r["store_id"],
                    "name_en": r["name_en"],
                    "tags_ar": r["tags_ar"],
                    "is_trending": r["is_trending"],
                    "last_time": r["last_time"].isoformat() if r["last_time"] else None,
                    "discount_value": r["discount_value"],
                    "recent_1h": int(r["recent_1h"]),
                    "recent_6h": int(r["recent_6h"]),
                    "recent_48h": int(r["recent_48h"]),
                    "hourly_mean": float(r["hourly_mean"]),
                    "hourly_stddev": float(r["hourly_stddev"]),
                } for r in rows
            ]

        # 2) المتاجر التي تنتهي خلال 7 أيام (فرص تجديد)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    m.id, m.store_id, m.name_en, m.last_time, m.public_coupon,
                    m.discount_value, m.is_trending,
                    COALESCE(v.recent_48h, 0) AS recent_48h
                FROM master m
                LEFT JOIN mv_store_velocity_48h v ON v.master_id = m.id
                WHERE m.last_time IS NOT NULL
                  AND m.last_time::timestamp > NOW()
                  AND m.last_time::timestamp < NOW() + INTERVAL '7 days'
                ORDER BY m.last_time ASC
                LIMIT 30
            """)
            rows = cur.fetchall()
            snapshot["expiring_within_7d"] = [
                {
                    "master_id": r["id"],
                    "store": r["store_id"],
                    "name_en": r["name_en"],
                    "last_time": r["last_time"].isoformat() if r["last_time"] else None,
                    "discount": r["discount_value"],
                    "is_trending": r["is_trending"],
                    "recent_48h": int(r["recent_48h"]),
                } for r in rows
            ]

        # 3) ملخص حركة الـ 48h حسب country + city (top 10)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT country_code, city, COUNT(*) AS events
                FROM action_logs
                WHERE action_time > NOW() - INTERVAL '48 hours'
                  AND quality_score >= 50
                  AND country_code IS NOT NULL
                GROUP BY country_code, city
                ORDER BY events DESC
                LIMIT 10
            """)
            snapshot["geo_distribution_48h"] = [
                {"country": r["country_code"], "city": r["city"], "events": int(r["events"])}
                for r in cur.fetchall()
            ]

    return snapshot


# ─────────────────────────────────────────────────────────────────────────────
# Prompt rendering + canonical hashing
# ─────────────────────────────────────────────────────────────────────────────

def render_prompt(snapshot: dict[str, Any]) -> str:
    """
    Render snapshot to a deterministic Arabic prompt. Same snapshot → same string
    → same hash → cache hit possible.
    """
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2)
    return (
        "هذي لقطة منصة DealPulse KSA لآخر 48 ساعة. "
        f"التوقّع المطلوب لـ {snapshot['horizon_hours']} ساعة قادمة.\n\n"
        f"البيانات:\n```json\n{canonical}\n```\n\n"
        "أعطني توجيهات تشغيلية حسب القواعد في الـ system prompt. "
        "ردك يجب أن يكون JSON صالح فقط، بدون شرح إضافي."
    )


def _hash_prompt(prompt_text: str) -> bytes:
    """SHA-256 of the canonical prompt. BYTEA = 32 bytes."""
    return hashlib.sha256(prompt_text.encode("utf-8")).digest()


# ─────────────────────────────────────────────────────────────────────────────
# Cache layer
# ─────────────────────────────────────────────────────────────────────────────

def _try_cache(prompt_hash: bytes) -> Optional[dict]:
    """Look up an exact-hash hit. Returns None on miss."""
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, response_text, response_json, tokens_input, tokens_output
                FROM llm_semantic_cache
                WHERE purpose = %s
                  AND prompt_hash = %s
                  AND expires_at > NOW()
                """,
                (PURPOSE, psycopg2_bytea(prompt_hash)),
            )
            row = cur.fetchone()
            if not row:
                return None

            cache_id, response_text, response_json, in_tok, out_tok = row
            # bump hit counter
            cur.execute(
                """
                UPDATE llm_semantic_cache
                SET hit_count   = hit_count + 1,
                    last_hit_at = NOW(),
                    tokens_saved = tokens_saved + COALESCE(%s, 0) + COALESCE(%s, 0)
                WHERE id = %s
                """,
                (in_tok, out_tok, cache_id),
            )
            return {
                "response_text": response_text,
                "response_json": response_json,
                "tokens_input": in_tok or 0,
                "tokens_output": out_tok or 0,
            }


def _save_to_cache(
    *, prompt_text: str, prompt_hash: bytes, response_text: str,
    response_json: dict | None, model: str, in_tokens: int, out_tokens: int,
) -> None:
    expires = datetime.now(timezone.utc) + timedelta(hours=CACHE_TTL_HOURS)
    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO llm_semantic_cache
                    (purpose, prompt_text, prompt_hash, response_text,
                     response_json, model, tokens_input, tokens_output,
                     expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (prompt_hash) DO UPDATE
                SET expires_at = EXCLUDED.expires_at,
                    response_text = EXCLUDED.response_text,
                    response_json = EXCLUDED.response_json
                """,
                (PURPOSE, prompt_text, psycopg2_bytea(prompt_hash),
                 response_text, Json(response_json) if response_json else None,
                 model, in_tokens, out_tokens, expires),
            )


def psycopg2_bytea(b: bytes):
    """psycopg2 wants memoryview or bytes — explicit conversion for clarity."""
    import psycopg2
    return psycopg2.Binary(b)


# ─────────────────────────────────────────────────────────────────────────────
# Persist directive
# ─────────────────────────────────────────────────────────────────────────────

def _persist_directive(
    *, snapshot: dict, prompt_hash: bytes, response_text: str,
    response_json: dict | None, model: str, in_tokens: int, out_tokens: int,
    cost_usd: float, cache_hit: bool,
) -> int:
    """
    INSERT into ai_directives + supersede previous active directives that
    share the same affected_master_ids (if response provides them).
    Returns the new directive id.
    """
    summary_ar = (response_json or {}).get("summary", "")[:280] if response_json else None
    confidence = (response_json or {}).get("confidence")
    affected_ids: list[int] = []
    if response_json and response_json.get("directives"):
        seen = set()
        for d in response_json["directives"]:
            for mid in (d.get("affected_master_ids") or []):
                if isinstance(mid, int) and mid not in seen:
                    seen.add(mid)
                    affected_ids.append(mid)

    with get_db_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ai_directives
                    (horizon_hours, input_window_hours, input_snapshot,
                     prompt_hash, model, directive_ar, summary_ar,
                     confidence, affected_master_ids,
                     token_input, token_output, cost_usd, cache_hit)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    DEFAULT_HORIZON_HOURS, 48, Json(snapshot),
                    psycopg2_bytea(prompt_hash), model, response_text,
                    summary_ar,
                    confidence if isinstance(confidence, (int, float)) else None,
                    affected_ids or None,
                    in_tokens, out_tokens, round(cost_usd, 5), cache_hit,
                ),
            )
            new_id = cur.fetchone()[0]

            # Supersede any previous active directive on overlapping master_ids
            if affected_ids:
                cur.execute(
                    """
                    UPDATE ai_directives
                    SET superseded_by = %s
                    WHERE superseded_by IS NULL
                      AND id <> %s
                      AND affected_master_ids && %s
                    """,
                    (new_id, new_id, affected_ids),
                )

    return new_id


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_directive(*, model: Optional[str] = None) -> dict[str, Any]:
    """
    Main entry. Returns:
        {
          "directive_id": int,
          "cache_hit": bool,
          "summary": str,
          "directives": list[dict],
          "model": str,
          "cost_usd": float,
          "tokens_input": int,
          "tokens_output": int,
          "refused_by_guardian": bool,
        }
    """
    snapshot = build_input_snapshot()
    prompt_text = render_prompt(snapshot)
    prompt_hash = _hash_prompt(prompt_text)

    # 1) Try cache (independent of provider — same prompt → same hash)
    cached = _try_cache(prompt_hash)
    if cached:
        _log.info("🎯 LLM cache HIT for directive")
        cached_model = "cache"
        directive_id = _persist_directive(
            snapshot=snapshot, prompt_hash=prompt_hash,
            response_text=cached["response_text"],
            response_json=cached["response_json"],
            model=cached_model, in_tokens=cached["tokens_input"],
            out_tokens=cached["tokens_output"], cost_usd=0.0,
            cache_hit=True,
        )
        return {
            "directive_id": directive_id,
            "cache_hit": True,
            "summary": (cached["response_json"] or {}).get("summary", ""),
            "directives": (cached["response_json"] or {}).get("directives", []),
            "model": cached_model,
            "provider": "cache",
            "fallback_used": False,
            "cost_usd": 0.0,
            "tokens_input": cached["tokens_input"],
            "tokens_output": cached["tokens_output"],
            "refused_by_guardian": False,
        }

    # 2) Cache miss → call LLM (Gemini primary, OpenRouter fallback)
    _log.info("🌐 LLM cache MISS — invoking call_llm()")
    result = call_llm(
        purpose=PURPOSE,
        system=SYSTEM_PROMPT_AR,
        user=prompt_text,
        model=model,            # None → backend picks its own default
        max_tokens=2048,
        temperature=0.4,
    )

    if result.refused_by_guardian or getattr(result, "refused_by_quota", False):
        reason = "quota_exhausted" if getattr(result, "refused_by_quota", False) else "financial_guardian"
        _log.warning("Directive generation refused (%s)", reason)
        return {
            "directive_id": None,
            "cache_hit": False,
            "summary": "",
            "directives": [],
            "model": result.model,
            "provider": result.provider,
            "fallback_used": result.fallback_used,
            "cost_usd": 0.0,
            "tokens_input": 0,
            "tokens_output": 0,
            "refused_by_guardian": True,
            "refused_reason": reason,
        }

    # 3) Parse JSON output (best-effort)
    response_json: dict | None = None
    text = (result.text or "").strip()
    if text.startswith("```"):
        # strip ```json ... ```
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        response_json = json.loads(text)
    except Exception:
        _log.warning("LLM returned non-JSON output — saving as text only")
        response_json = None

    # 4) Save cache + persist directive
    _save_to_cache(
        prompt_text=prompt_text, prompt_hash=prompt_hash,
        response_text=result.text, response_json=response_json,
        model=result.model,
        in_tokens=result.tokens_input, out_tokens=result.tokens_output,
    )

    directive_id = _persist_directive(
        snapshot=snapshot, prompt_hash=prompt_hash,
        response_text=result.text, response_json=response_json,
        model=result.model, in_tokens=result.tokens_input,
        out_tokens=result.tokens_output, cost_usd=result.cost_usd,
        cache_hit=False,
    )

    return {
        "directive_id": directive_id,
        "cache_hit": False,
        "summary": (response_json or {}).get("summary", "") if response_json else "",
        "directives": (response_json or {}).get("directives", []) if response_json else [],
        "model": result.model,
        "provider": result.provider,
        "fallback_used": result.fallback_used,
        "cost_usd": result.cost_usd,
        "tokens_input": result.tokens_input,
        "tokens_output": result.tokens_output,
        "refused_by_guardian": False,
    }
