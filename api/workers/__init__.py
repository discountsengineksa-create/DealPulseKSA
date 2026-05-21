"""
Background workers for Week 2:
  - velocity_aggregator: consumes events:raw stream, fills coupon_velocity_snapshots
  - matview_refresher:   refreshes mv_store_velocity_48h every minute
  - spike_detector:      scans z-scores, enqueues spike alerts every 5 minutes
  - alert_dispatcher:    emails pending ai_alerts every 30 seconds

Entry point: scheduler.start_workers() — called once from bot_app.py on_startup.
"""
