---
name: Railway Production Deployment
description: Working Railway production setup for DealPulseKSA — services, URLs, and stable git tag for rollback
type: project
originSessionId: bc31e9f1-2d0f-42d9-93eb-2865b8e8471b
---
Project deployed to Railway as a single unified service called `DealPulseKSA` (not separate bot/api/dashboard).

**Why:** The original Procfile defined 3 services (api/bot/dashboard) but on Railway we consolidated bot+api+miniapp into one FastAPI app (`bot_app.py`) running `uvicorn bot_app:app --workers 4`. The dashboard remains a separate Streamlit service. The old `bot` and `api` services in Railway were deleted on 2026-05-08.

**How to apply:**
- Production URL: `https://dealpulseksa-production.up.railway.app`
- Endpoints on the unified service: `/health`, `/miniapp`, `/api/v1/coupons/`, `/api/v1/track`, `/telegram/webhook/{secret}`, `/logo.png` (whitelist static)
- GitHub repo: `discountsengineksa-create/DealPulseKSA`, branch `main` (auto-deploys on push)
- Stable rollback tag: `v1.0.0-stable` (commit `0bd54cb`) — first verified-working production release
- Telegram Mini App URL must be set in BotFather to `/miniapp` path on this domain
- Webhook is registered idempotently in `on_startup` (checks `bot.get_webhook_info().url` first to avoid multi-worker race condition)
