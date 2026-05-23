"""
Cross-cutting ops helpers (migration_016):
  • audit_log()            — يكتب صفّاً في pdpl_audit_log (best-effort، لا يرمي).
  • is_quiet_now()         — هل الوقت الآن ضمن نافذة هدوء تكتم الإيميل؟
  • log_experiment_event() — يسجّل impression/click/conversion لتجربة A/B.
  • experiment_results()   — يجمّع نتائج التجارب لكل arm.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]

from psycopg2.extras import Json, RealDictCursor

from api.db import get_db_context

_log = logging.getLogger("dp.ops")


# ── Audit (PDPL) ────────────────────────────────────────────────────────────
def audit_log(*, action: str, actor: str = "admin", target: str | None = None,
              status: str = "ok", meta: dict | None = None) -> None:
    """يسجّل عملية أدمن. best-effort — لا يُفشل العملية الأصلية أبداً."""
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO pdpl_audit_log (actor, action, target, status, meta)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (actor[:80], action[:60], (target or "")[:160] or None,
                     status[:20], Json(meta) if meta else None),
                )
    except Exception as exc:
        _log.warning("audit_log failed (%s): %s", action, exc)


# ── Quiet hours ─────────────────────────────────────────────────────────────
def _hour_in_window(hour: int, start: int, end: int) -> bool:
    if start == end:
        return False
    if start < end:
        return start <= hour < end
    # نافذة عابرة لمنتصف الليل (مثل 23 → 7)
    return hour >= start or hour < end


def is_quiet_now(channel: str = "email") -> tuple[bool, Optional[str]]:
    """يرجّع (True, label) لو الوقت الآن ضمن نافذة هدوء فعّالة تكتم القناة."""
    try:
        with get_db_context() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT label, start_hour, end_hour, timezone, channels "
                    "FROM alert_quiet_hours WHERE active = TRUE"
                )
                rows = cur.fetchall()
    except Exception as exc:
        _log.warning("is_quiet_now check failed: %s — assuming not quiet", exc)
        return False, None

    for r in rows:
        chans = r.get("channels") or []
        if channel not in chans:
            continue
        tzname = r.get("timezone") or "Asia/Riyadh"
        try:
            now = datetime.now(ZoneInfo(tzname)) if ZoneInfo else datetime.utcnow()
        except Exception:
            now = datetime.utcnow()
        if _hour_in_window(now.hour, int(r["start_hour"]), int(r["end_hour"])):
            return True, r.get("label")
    return False, None


# ── Experiments (A/B) ───────────────────────────────────────────────────────
def log_experiment_event(*, surface: str, arm: str, event_type: str = "impression",
                         ref_id: int | None = None, value: float = 0.0) -> None:
    """يسجّل حدث تجربة للـ surface المحدّد (لو فيه تجربة نشطة عليه). best-effort."""
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM ai_experiments WHERE surface = %s AND active = TRUE LIMIT 1",
                    (surface,),
                )
                row = cur.fetchone()
                if not row:
                    return
                cur.execute(
                    """
                    INSERT INTO ai_experiment_events (experiment_id, arm, event_type, ref_id, value)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (row[0], str(arm)[:40], event_type[:20], ref_id, value),
                )
    except Exception as exc:
        _log.warning("log_experiment_event failed (%s/%s): %s", surface, arm, exc)


def experiment_results(limit: int = 50) -> list[dict[str, Any]]:
    """نتائج كل تجربة لكل arm: عدد الـ impressions/clicks/conversions + القيمة."""
    with get_db_context() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT e.name AS experiment, e.surface, ev.arm,
                       COUNT(*) FILTER (WHERE ev.event_type = 'impression') AS impressions,
                       COUNT(*) FILTER (WHERE ev.event_type = 'click')      AS clicks,
                       COUNT(*) FILTER (WHERE ev.event_type = 'conversion') AS conversions,
                       COALESCE(SUM(ev.value), 0) AS total_value
                FROM ai_experiments e
                LEFT JOIN ai_experiment_events ev ON ev.experiment_id = e.id
                GROUP BY e.name, e.surface, ev.arm
                ORDER BY e.name, ev.arm
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
