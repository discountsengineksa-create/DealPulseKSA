"""
Spike detector — scans mv_store_velocity_48h for stores with an
unusual surge in the last hour AND whose coupon is about to expire.

Spike criteria (all must hold):
  • hourly_mean > 5           (ignore tiny stores — noise)
  • hourly_stddev > 0          (avoid div-by-zero)
  • z = (recent_1h - hourly_mean) / hourly_stddev > 2.5
  • master.last_time is between NOW and NOW + 24h  (near expiry only)

Every spike becomes one row in ai_alerts with a deterministic
idempotency_key — so the same store can't trigger duplicate emails
in the same hour bucket, no matter how many times the detector runs.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from api.db import get_db_context

_log = logging.getLogger("dp.spike")

Z_THRESHOLD = 2.5
MIN_HOURLY_MEAN = 5
NEAR_EXPIRY_HOURS = 24


def _idempotency_key(master_id: int) -> str:
    """spike:{master_id}:{YYYY-MM-DDTHH}:near_expiry — one per hour bucket."""
    hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    return f"spike:{master_id}:{hour}:near_expiry"


def _format_ar_body(row: dict) -> tuple[str, str]:
    """Return (title, html_body) for the email."""
    store = row["store_id"]
    coupon = row.get("public_coupon") or "—"
    z = row["z_score"]
    recent_1h = row["recent_1h"]
    mean = row["hourly_mean"]
    hours_left = row["hours_to_expiry"]

    title = f"🔥 ذروة بيع — {store} (كود ينتهي خلال {hours_left:.1f} ساعة)"

    body = (
        f"<p>كود <b>{store}</b> يشهد إقبالاً غير اعتيادي:</p>"
        f"<ul>"
        f"  <li>التفاعل في آخر ساعة: <b>{recent_1h}</b> حدث</li>"
        f"  <li>المتوسط الطبيعي بالساعة: <b>{mean:.1f}</b></li>"
        f"  <li>z-score: <b>{z:.2f}</b> (العتبة {Z_THRESHOLD})</li>"
        f"  <li>الكوبون الحالي: <code>{coupon}</code></li>"
        f"  <li>ينتهي خلال: <b>{hours_left:.1f}</b> ساعة</li>"
        f"</ul>"
        f"<p>هذي فرصة تجديد كود بديل قبل ينتهي — "
        f"الزخم الحالي سيوفر أعلى تحويل ممكن.</p>"
    )
    return title, body


def detect_spikes() -> int:
    """
    One-shot scan. Returns number of NEW alerts created (existing
    idempotency keys are silently skipped via ON CONFLICT).
    Call from a scheduler every 5 minutes.
    """
    sql = """
        SELECT
            v.master_id,
            v.recent_1h,
            v.hourly_mean,
            v.hourly_stddev,
            (v.recent_1h - v.hourly_mean) / NULLIF(v.hourly_stddev, 0) AS z_score,
            m.store_id,
            m.public_coupon,
            m.last_time,
            EXTRACT(EPOCH FROM (m.last_time::timestamp + INTERVAL '24 hour' - NOW())) / 3600.0 AS hours_to_expiry
        FROM mv_store_velocity_48h v
        JOIN master m ON m.id = v.master_id
        WHERE v.hourly_mean > %s
          AND v.hourly_stddev > 0
          AND (v.recent_1h - v.hourly_mean) / NULLIF(v.hourly_stddev, 0) > %s
          AND m.last_time IS NOT NULL
          AND m.last_time::timestamp > NOW()
          AND m.last_time::timestamp < NOW() + INTERVAL '%s hours'
    """

    new_alerts = 0
    try:
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (MIN_HOURLY_MEAN, Z_THRESHOLD, NEAR_EXPIRY_HOURS))
                rows = cur.fetchall()
                col_names = [d[0] for d in cur.description]

            for raw_row in rows:
                row = dict(zip(col_names, raw_row))
                title, body = _format_ar_body(row)
                key = _idempotency_key(row["master_id"])
                context = {
                    "z_score": float(row["z_score"]),
                    "recent_1h": int(row["recent_1h"]),
                    "hourly_mean": float(row["hourly_mean"]),
                    "hourly_stddev": float(row["hourly_stddev"]),
                    "hours_to_expiry": float(row["hours_to_expiry"]),
                    "last_time": str(row["last_time"]),
                }
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO ai_alerts
                            (alert_type, master_id, severity, idempotency_key,
                             title, body, context_json, dispatch_channel)
                        VALUES ('spike_near_expiry', %s, 'critical', %s,
                                %s, %s, %s::jsonb, 'email')
                        ON CONFLICT (idempotency_key) DO NOTHING
                        RETURNING id
                        """,
                        (row["master_id"], key, title, body, json.dumps(context)),
                    )
                    inserted = cur.fetchone()
                if inserted:
                    new_alerts += 1
                    _log.info("Spike alert queued for master_id=%s z=%.2f",
                              row["master_id"], row["z_score"])

    except Exception as exc:
        _log.error("Spike detection failed: %s", exc)
        return 0

    if new_alerts:
        _log.info("Spike detector: %d new alert(s) queued", new_alerts)
    return new_alerts
