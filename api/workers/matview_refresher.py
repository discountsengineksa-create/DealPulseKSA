"""
Materialized-view refresher.

`mv_store_velocity_48h` holds rolling 1h/6h/48h aggregates with a
hourly mean+stddev baseline used by the spike detector. We rebuild it
every minute. CONCURRENTLY = readers (spike_detector, dashboard) never
see an empty matview during refresh — they just see the previous
snapshot until the new one is ready.
"""
from __future__ import annotations

import logging

from api.db import get_db_context

_log = logging.getLogger("dp.matview")


def refresh_velocity_matview() -> None:
    """One-shot refresh. Called on a schedule (every minute)."""
    try:
        with get_db_context() as conn:
            conn.autocommit = True  # REFRESH MV CONCURRENTLY cannot run inside a transaction
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_store_velocity_48h")
        _log.debug("mv_store_velocity_48h refreshed")
    except Exception as exc:
        # Most common transient error: matview is empty (first run before
        # any snapshots). Fall back to non-concurrent refresh once.
        msg = str(exc)
        if "could not be refreshed concurrently" in msg or "is not populated" in msg:
            try:
                with get_db_context() as conn:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute("REFRESH MATERIALIZED VIEW mv_store_velocity_48h")
                _log.info("mv_store_velocity_48h initial refresh (non-concurrent)")
                return
            except Exception as exc2:
                _log.error("Initial matview refresh failed: %s", exc2)
        else:
            _log.error("matview refresh failed: %s", exc)
