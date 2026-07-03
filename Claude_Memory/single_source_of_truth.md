---
name: single-source-of-truth
description: ONE database (Railway Postgres) + ONE dashboard (Railway-hosted) — the local test DB was deleted; no more local/prod confusion
metadata: 
  node_type: memory
  type: project
  originSessionId: 981b8ddc-71cf-40ba-bb27-30bdfc73c992
---

Decided 2026-05-29: the product must be a single source of truth for sale to companies — no "old/new" DB, no two dashboards. The test/experimental phase is over.

**Database — DONE:** There is now ONE database = the **Railway Postgres** (`turntable.proxy.rlwy.net/railway`, ~25 real stores incl. نمشي ×6). The local `localhost/discounts_engine` test DB (16 dummy stores like '1','2','999','تجربة الترند') was **permanently dropped**. The local `.env` now has ONLY `DATABASE_URL` (= the Railway URL, copied from `MIGRATION_DATABASE_URL`); the `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT` localhost fallback lines were removed. So dashboard/bot/api (which all read `DATABASE_URL` first) can ONLY hit Railway — even when run locally.

**Why this mattered:** repeated confusion where a fix/login/password change happened against the wrong DB. The local dashboard had been reading the stale localhost DB while bot/web/mini/social read Railway — so real data (نمشي) "didn't show" in the dashboard. Root cause was `.env` having no `DATABASE_URL` → silent localhost fallback. See [[bug-fixes]] entry #10.

**Dashboard — pending user action on Railway:** THE official dashboard = the Railway-hosted service `dashboard-production-6e9f.up.railway.app`. Local `streamlit run dashboard.py` = dev only. User must set on the Railway dashboard service Variables: `DATABASE_URL=${{Postgres.DATABASE_URL}}` (shared Postgres reference), `username`, `password`. Login is now UNIFIED to **admin / DealPulse@2026** everywhere: local `.streamlit/secrets.toml` holds the bcrypt hash of `DealPulse@2026`, and prod Railway env vars are `username=admin` / `password=DealPulse@2026` (already set). (Note: `123456` is the postgres DB password, NOT a dashboard login — never typed at a login screen.) The Railway dashboard service already has DATABASE_URL/username/password/Cloudinary/ADMIN_SHARED_SECRET/INTERNAL_API_URL set.

**How to apply:** Never reintroduce a second DB or a localhost data fallback. When something "doesn't show", the DB is Railway — don't query localhost. The bot still has a dead hardcoded localhost fallback in code (harmless now; clean up if touching bot DB config). CLAUDE.md's "keep .env in sync with hardcoded bot values" note is now obsolete for the localhost path.
