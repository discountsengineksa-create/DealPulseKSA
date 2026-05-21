"""
Worker orchestration — single entry point called from bot_app.on_startup.

Boots up:
  1. A background thread running the velocity_aggregator stream consumer
     (long-lived, blocks on XREADGROUP).
  2. An APScheduler BackgroundScheduler with three cron-like jobs:
       • matview refresh        every 1 minute
       • spike detector          every 5 minutes
       • alert dispatcher        every 30 seconds

start_workers() is idempotent — calling it twice on the same process is
a no-op. Designed for single-worker uvicorn (default on Railway). For
multi-worker, a Redis lock per job would be needed; that's deferred.
"""
from __future__ import annotations

import logging
import os
import threading

from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

from api.workers.alert_dispatcher import dispatch_pending_alerts
from api.workers.matview_refresher import refresh_velocity_matview
from api.workers.spike_detector import detect_spikes
from api.workers.velocity_aggregator import run_velocity_consumer

_log = logging.getLogger("dp.scheduler")

# Sentinel used by tests and by ourselves to avoid double-start
_started = False
_started_lock = threading.Lock()

# Configurable via env (Railway can override without redeploy)
MATVIEW_REFRESH_MINUTES = int(os.getenv("WORKER_MATVIEW_REFRESH_MIN", "1"))
SPIKE_DETECT_MINUTES    = int(os.getenv("WORKER_SPIKE_DETECT_MIN", "5"))
ALERT_DISPATCH_SECONDS  = int(os.getenv("WORKER_ALERT_DISPATCH_SEC", "30"))

_scheduler: BackgroundScheduler | None = None
_consumer_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def start_workers() -> None:
    """Boot the aggregator thread + scheduled jobs. Safe to call multiple times."""
    global _started, _scheduler, _consumer_thread, _stop_event
    with _started_lock:
        if _started:
            _log.debug("Workers already started — skip")
            return
        _started = True

    if os.getenv("DISABLE_WORKERS") == "1":
        _log.warning("DISABLE_WORKERS=1 — skipping worker bootstrap")
        return

    # 1) Velocity aggregator (long-lived stream consumer)
    _stop_event = threading.Event()
    _consumer_thread = threading.Thread(
        target=run_velocity_consumer,
        kwargs={"stop_event": _stop_event},
        name="velocity-aggregator",
        daemon=True,
    )
    _consumer_thread.start()
    _log.info("✅ velocity_aggregator thread started")

    # 2) APScheduler for the three cron jobs
    _scheduler = BackgroundScheduler(
        timezone="UTC",
        job_defaults={
            "coalesce": True,           # if missed runs pile up, run only once
            "max_instances": 1,         # never run two copies of the same job in parallel
            "misfire_grace_time": 60,   # forgiven within 60s
        },
    )

    _scheduler.add_job(
        refresh_velocity_matview,
        trigger="interval",
        minutes=MATVIEW_REFRESH_MINUTES,
        id="matview_refresh",
        name="Refresh mv_store_velocity_48h",
        replace_existing=True,
    )

    _scheduler.add_job(
        detect_spikes,
        trigger="interval",
        minutes=SPIKE_DETECT_MINUTES,
        id="spike_detect",
        name="Detect velocity spikes",
        replace_existing=True,
    )

    _scheduler.add_job(
        dispatch_pending_alerts,
        trigger="interval",
        seconds=ALERT_DISPATCH_SECONDS,
        id="alert_dispatch",
        name="Dispatch pending email alerts",
        replace_existing=True,
    )

    _scheduler.start()
    _log.info(
        "✅ APScheduler started — matview/%dm, spike/%dm, dispatch/%ds",
        MATVIEW_REFRESH_MINUTES, SPIKE_DETECT_MINUTES, ALERT_DISPATCH_SECONDS,
    )


def stop_workers() -> None:
    """Graceful shutdown — currently only used by tests."""
    global _started
    if _stop_event is not None:
        _stop_event.set()
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
    _started = False
    _log.info("Workers stopped")
