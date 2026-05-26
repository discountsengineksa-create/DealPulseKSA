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
from api.workers.directive_generator import run_directive_cycle
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
DIRECTIVE_HOURS         = int(os.getenv("WORKER_DIRECTIVE_HOURS", "3"))
# Week 5-6 — SEO generator
SEO_DISCOVERY_HOURS     = int(os.getenv("WORKER_SEO_DISCOVERY_HOURS", "12"))
SEO_GENERATE_HOURS      = int(os.getenv("WORKER_SEO_GENERATE_HOURS", "6"))
SEO_GENERATE_BATCH      = int(os.getenv("SEO_GENERATE_BATCH", "3"))
SEO_AUTOGEN_ENABLED     = os.getenv("SEO_AUTOGEN_ENABLED") == "1"
# Week 7-8 — social listener (scoring/matching/response prep — مجاني، بلا LLM)
SOCIAL_PROCESS_MINUTES  = int(os.getenv("WORKER_SOCIAL_PROCESS_MIN", "10"))
SOCIAL_PROCESS_BATCH    = int(os.getenv("SOCIAL_PROCESS_BATCH", "20"))
# محرك الفرص — Google Trends refresh كل ساعة افتراضياً
TRENDS_REFRESH_HOURS    = int(os.getenv("WORKER_TRENDS_REFRESH_HOURS", "1"))

_scheduler: BackgroundScheduler | None = None
_consumer_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None


def _seo_discovery_cycle() -> None:
    """Week 5-6 — مرحلة مجانية: تجميع الترند الداخلي + مطابقة وإنشاء وظائف."""
    from api.seo.matcher import match_and_enqueue
    from api.seo.trends import aggregate_internal_search
    aggregate_internal_search()
    match_and_enqueue()


def _seo_generation_cycle() -> None:
    """Week 5-6 — مرحلة LLM (تستهلك الميزانية): توليد صفحات من الوظائف المنتظرة."""
    from api.seo.generator import process_pending_jobs
    process_pending_jobs(batch=SEO_GENERATE_BATCH)


def _social_listener_cycle() -> None:
    """
    Week 7-8 — دورة الرصد الاجتماعي كل 10 دقائق:
      1. poll Reddit (تلتقط mentions جديدة → تخزّنها بـ status='new')
      2. process_new_signals → score, match, generate draft replies
    """
    from api.social_listener.pollers import run_all_pollers
    from api.social_listener.responder import process_new_signals

    try:
        run_all_pollers()
    except Exception as exc:
        _log.warning("pollers cycle failed (non-fatal): %s", exc)

    process_new_signals(batch=SOCIAL_PROCESS_BATCH)


def _trends_refresh_cycle() -> None:
    """
    محرك الفرص — يجلب درجة Google Trends لكل keyword نشط في
    seo_opportunity_keywords كل ساعة. أي فشل لـ pytrends يُلتقط داخلياً
    ويُسجَّل في last_error بدل كسر الـ scheduler.
    """
    from api.seo.trends_puller import refresh_all_active_keywords
    try:
        refresh_all_active_keywords()
    except Exception as exc:
        _log.warning("trends refresh cycle failed (non-fatal): %s", exc)


def _llm_cache_cleanup_cycle() -> None:
    """
    تنظيف صفوف llm_semantic_cache المنتهية الصلاحية (migration_022).
    يمنع تراكم صفوف ميتة في DB. يدعو الدالة الـ Postgres SQL إذا وُجدت
    (cleanup_expired_llm_cache)، وإلا DELETE مباشرة.
    """
    try:
        from api.db import get_db_context
        with get_db_context() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT cleanup_expired_llm_cache()")
                deleted = cur.fetchone()
                if deleted:
                    _log.info("LLM cache cleanup: removed %s expired rows", deleted[0])
    except Exception as exc:
        # لو دالة Postgres غير موجودة (migration_022 لم تُطبَّق بعد) نستخدم DELETE
        try:
            from api.db import get_db_context
            with get_db_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM llm_semantic_cache WHERE expires_at < NOW()")
        except Exception as exc2:
            _log.warning("llm cache cleanup failed (non-fatal): %s / %s", exc, exc2)


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

    # NOTE: APScheduler quirk — passing next_run_time=None to add_job() PAUSES
    # the job (never auto-fires). To delay first run to "now + interval" we
    # must OMIT next_run_time entirely (the trigger's get_next_fire_time will
    # then return now + interval). This used to be the bug that kept
    # social_listener / directive_generator / seo_* jobs silent for days.

    # Week 3 — LLM directive generator (every 3 hours by default)
    _scheduler.add_job(
        run_directive_cycle,
        trigger="interval",
        hours=DIRECTIVE_HOURS,
        id="directive_generator",
        name="Generate LLM operational directives",
        replace_existing=True,
    )

    # Week 5-6 — SEO discovery (مجاني: trends + match) كل 12 ساعة
    _scheduler.add_job(
        _seo_discovery_cycle,
        trigger="interval",
        hours=SEO_DISCOVERY_HOURS,
        id="seo_discovery",
        name="SEO trend discovery + store match",
        replace_existing=True,
    )

    # Week 5-6 — SEO generation (يستهلك ميزانية LLM) — محكوم بـ SEO_AUTOGEN_ENABLED
    if SEO_AUTOGEN_ENABLED:
        _scheduler.add_job(
            _seo_generation_cycle,
            trigger="interval",
            hours=SEO_GENERATE_HOURS,
            id="seo_generate",
            name="SEO LLM page generation",
            replace_existing=True,
        )

    # Week 7-8 — social listener processing (مجاني) كل 10 دقائق
    # Run the first cycle ~30s after boot so leads start appearing quickly
    # instead of waiting the full 10-minute interval after every redeploy.
    from datetime import datetime, timedelta, timezone
    _scheduler.add_job(
        _social_listener_cycle,
        trigger="interval",
        minutes=SOCIAL_PROCESS_MINUTES,
        id="social_listener",
        name="Process social signals + prepare responses",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
    )

    # محرك الفرص — refresh Google Trends لكل active keyword كل ساعة
    _scheduler.add_job(
        _trends_refresh_cycle,
        trigger="interval",
        hours=TRENDS_REFRESH_HOURS,
        id="trends_refresh",
        name="Refresh Google Trends scores for opportunity keywords",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=90),
    )

    # تنظيف llm_semantic_cache المنتهي — كل ساعة (migration_022).
    # يمنع تراكم صفوف ميتة في DB ويُحرّر مساحة قرص دورياً.
    _scheduler.add_job(
        _llm_cache_cleanup_cycle,
        trigger="interval",
        hours=1,
        id="llm_cache_cleanup",
        name="Clean expired llm_semantic_cache rows",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

    _scheduler.start()
    _log.info(
        "✅ APScheduler started — matview/%dm, spike/%dm, dispatch/%ds, directive/%dh, "
        "seo_discovery/%dh, seo_generate=%s, social/%dm, trends/%dh",
        MATVIEW_REFRESH_MINUTES, SPIKE_DETECT_MINUTES,
        ALERT_DISPATCH_SECONDS, DIRECTIVE_HOURS,
        SEO_DISCOVERY_HOURS, "on/%dh" % SEO_GENERATE_HOURS if SEO_AUTOGEN_ENABLED else "off",
        SOCIAL_PROCESS_MINUTES, TRENDS_REFRESH_HOURS,
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
