"""
Velocity aggregator — long-running stream consumer.

Reads events from Redis Stream `events:raw` (XADD'd by /track endpoint)
and UPSERTs them into 5-minute buckets on coupon_velocity_snapshots.

Design choices:
  • Consumer group "aggregators" → multiple workers can share load via
    XREADGROUP without duplicate processing. XACK confirms each batch.
  • Bucket = floor(now / 5min). The handler does an UPSERT with
    INCREMENT semantics so concurrent events on the same store/bucket
    add up safely.
  • Low-quality events (quality < 50) are persisted to action_logs
    but excluded here from velocity counters (anti-fraud).
  • Failures in one event don't block the rest of the batch.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from api.db import get_db_context  # see note below — falls back to direct conn
from api.utils.redis_client import get_redis

_log = logging.getLogger("dp.aggregator")

STREAM = "events:raw"
GROUP = "aggregators"
CONSUMER = "consumer-1"
BLOCK_MS = 5000
BATCH_SIZE = 100
QUALITY_FLOOR = 50


def _ensure_group() -> None:
    """Create consumer group idempotently. MKSTREAM bootstraps an empty stream."""
    r = get_redis()
    try:
        r.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        _log.info("Created consumer group %s on %s", GROUP, STREAM)
    except Exception as exc:
        # BUSYGROUP means already exists — fine.
        if "BUSYGROUP" not in str(exc):
            _log.warning("xgroup_create unexpected: %s", exc)


def _bucket_floor_utc(minute_size: int = 5) -> datetime:
    """Round current UTC time down to the nearest N-minute bucket."""
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    floored_minute = (now.minute // minute_size) * minute_size
    return now.replace(minute=floored_minute)


def _process_event(fields: dict[str, str], conn) -> None:
    """Apply one event to coupon_velocity_snapshots (upsert + increment)."""
    store_id = fields.get("store_id")
    action = fields.get("action")
    quality = int(fields.get("quality", "100"))
    country = fields.get("country") or None

    if not store_id or not action:
        return  # malformed
    if quality < QUALITY_FLOOR:
        return  # anti-fraud filter

    bucket_start = _bucket_floor_utc(5)

    # Resolve master_id from store_id (skip if store deleted)
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM master WHERE store_id = %s", (store_id,))
        row = cur.fetchone()
        if not row:
            return
        master_id = row[0]

    # Increment counters per action_type. ON CONFLICT does an atomic UPDATE
    # so concurrent workers on the same bucket sum correctly.
    clicks_delta = 1 if action == "click_link" else 0
    copies_delta = 1 if action == "copy_coupon" else 0
    searches_delta = 1 if action == "search" else 0

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO coupon_velocity_snapshots
                (master_id, bucket_start, bucket_minutes,
                 clicks, copies, searches,
                 unique_visitors, top_country, avg_quality_score)
            VALUES (%s, %s, 5, %s, %s, %s, 1, %s, %s)
            ON CONFLICT (master_id, bucket_start, bucket_minutes) DO UPDATE
            SET clicks   = coupon_velocity_snapshots.clicks   + EXCLUDED.clicks,
                copies   = coupon_velocity_snapshots.copies   + EXCLUDED.copies,
                searches = coupon_velocity_snapshots.searches + EXCLUDED.searches,
                unique_visitors  = coupon_velocity_snapshots.unique_visitors + 1,
                avg_quality_score = (
                    (COALESCE(coupon_velocity_snapshots.avg_quality_score, 100)
                     * coupon_velocity_snapshots.unique_visitors + EXCLUDED.avg_quality_score)
                    / NULLIF(coupon_velocity_snapshots.unique_visitors + 1, 0)
                )::smallint
            """,
            (master_id, bucket_start, clicks_delta, copies_delta,
             searches_delta, country, quality),
        )


def run_velocity_consumer(stop_event=None) -> None:
    """
    Long-running loop. Call from a background thread.
    `stop_event` is an optional threading.Event for graceful shutdown.
    """
    _ensure_group()
    r = get_redis()
    _log.info("Velocity aggregator started — consuming %s as %s", STREAM, CONSUMER)

    while True:
        if stop_event is not None and stop_event.is_set():
            _log.info("Velocity aggregator received stop signal — exiting")
            return

        try:
            # Block up to BLOCK_MS waiting for new entries (>).
            entries = r.xreadgroup(
                groupname=GROUP,
                consumername=CONSUMER,
                streams={STREAM: ">"},
                count=BATCH_SIZE,
                block=BLOCK_MS,
            )
        except Exception as exc:
            _log.error("XREADGROUP failed: %s — sleeping 2s", exc)
            time.sleep(2)
            continue

        if not entries:
            continue  # idle tick; loop again

        # entries is [(stream_name, [(id, {field: val}), ...])]
        ack_ids: list[str] = []
        try:
            with get_db_context() as conn:
                for _stream_name, items in entries:
                    for entry_id, fields in items:
                        try:
                            _process_event(fields, conn)
                            ack_ids.append(entry_id)
                        except Exception as exc:
                            _log.error("Event %s failed: %s", entry_id, exc)
                            # leave un-ACKed → eligible for retry by another consumer
        except Exception as exc:
            _log.error("DB batch failed: %s — entries left un-ACKed", exc)
            time.sleep(1)
            continue

        if ack_ids:
            try:
                r.xack(STREAM, GROUP, *ack_ids)
            except Exception as exc:
                _log.error("XACK failed: %s", exc)
