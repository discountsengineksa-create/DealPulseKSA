---
name: Railway Scheduler Worker Setup
description: scheduler-worker service config — separate Railway config file, cron limit, healthcheck override
type: project
originSessionId: 1dac0e43-3aaf-4594-8267-21042476a720
---
A separate Railway service `scheduler-worker` runs `api/workers/broadcast_scheduler.py` on cron to dispatch due broadcast jobs from `broadcast_schedules` table.

**Why:** The main `DealPulseKSA` service is a long-running FastAPI app (uvicorn + healthcheck on `/health`). The scheduler is a one-shot script that exits after each run. Putting both on the same Railway config breaks because `railway.toml` forces `healthcheckPath = "/health"` which the worker has no HTTP endpoint to satisfy.

**How to apply:**
- Worker service uses a **separate config file**: `railway.worker.toml` (no healthcheck, `restartPolicyType = "never"`)
- Configured in Railway → scheduler-worker → Settings → Config-as-code → Config Path = `railway.worker.toml`
- Start Command: `python -m api.workers.broadcast_scheduler`
- Cron Schedule: `*/5 * * * *` (Railway minimum is **5 minutes** — `* * * * *` is rejected even though the worker doc says "every minute")
- Variables use `${{Postgres.DATABASE_URL}}` and `${{DealPulseKSA.<var>}}` references; `TRACKING_BASE_URL` is the hardcoded production URL
- The `Serverless is not available for services that have a cron schedule` warning is informational, ignore it
- Practical consequence: scheduled broadcasts have up to 5 min latency vs. the scheduled time — acceptable for marketing
- **Verified end-to-end 2026-06-07**: user scheduled email for 15:30 KSA, scheduler-worker picked it up in the matching cron run, email arrived at the scheduled minute without manual intervention. Full automatic path is working.
