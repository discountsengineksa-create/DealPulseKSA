# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 🧠 **READ FIRST, EVERY SESSION: [`AGENT_PLAYBOOK.md`](AGENT_PLAYBOOK.md).** It is
> the working method the owner expects — diagnose root cause not symptoms, verify
> end-to-end, be honest about ceilings, and keep the shared `Claude_Memory/` up to
> date. The difference between solving a problem in one pass vs. failing six times
> is that playbook, not raw intelligence. Also read `Claude_Memory/MEMORY.md` (the
> memory index) and open any entry relevant to your task before touching code.

## Running the Project

```bash
# Admin dashboard (opens at localhost:8501)
streamlit run dashboard.py

# Telegram bot
python deal_pulse_bot.py

# Bot with auto-restart on crash (Windows)
# Rename run_ghost.bat.txt to run_ghost.bat, then double-click or run:
run_ghost.bat
```

Database credentials come from `.env` (`DATABASE_URL` for Railway prod, or `DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT` for local Postgres). No component hardcodes credentials — everything reads from environment variables.

## Architecture

Four runnable entrypoints share one PostgreSQL database:

- **`dashboard.py`** — Streamlit admin interface. A single **14,967-line** file; all **35 pages** are implemented as one long `if/elif` chain keyed on `page = st.sidebar.radio(...)`. No page routing abstraction. **⚠️ `main = production Railway` — see `AGENT_PLAYBOOK.md` §4.9 for the pre-push safety protocol.**
- **`deal_pulse_bot.py`** — Telegram bot (~2,376 lines) using `pyTelegramBotAPI` (`telebot`). **🔒 FROZEN — no edits without per-change explicit permission** (`bot_frozen_lock.md`).
- **`bot_app.py`** — Production Railway entrypoint (~412 lines). Combines bot + FastAPI (11 routers) + Mini App into one service.
- **`api/main.py`** — API-only entrypoint for local dev (`uvicorn api.main:app --port 8000`). Production runs `bot_app.py` instead.
- **PostgreSQL** (Railway prod, via `DATABASE_URL`) — **~67 tables** after `migration_049` dropped 9 abandoned tables. Local `discounts_engine` on `localhost:5432` is a dummy/test DB only. The `master` table is the source of truth for all store/coupon data.

## Database Patterns

**Connection pool** (dashboard, ~line 906–989): `psycopg2.pool.ThreadedConnectionPool` wrapped in a `_PooledConn` class with `__del__` safety net (returns to pool on GC even if `close()` was skipped due to exception). Credentials come from `DATABASE_URL` in `.env` — never hardcoded.

```python
conn = get_conn()          # returns _PooledConn — checks out from pool
# ... use conn (cursor, execute) ...
conn.close()               # returns connection to pool (not real close)
# Also supports: with get_conn() as conn:   # auto commit/rollback
```

**Transaction state**: Pages that only read data still call `conn.rollback()` (or `conn.autocommit = True`) at the top to clear any aborted-transaction state left from a previous error. This is a deliberate recurring pattern — do not remove it.

**`store_tags` column** is declared as plain `text` (NOT `text[]`), but data is written in PostgreSQL array-literal format `'{tag1,tag2,tag3}'`. Calls like `unnest(store_tags)`, `array_to_string(store_tags, ',')`, or `%s = ANY(store_tags)` will fail at runtime — the column is text, the operator expects array. To work with it in SQL, convert first: `string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',')`. For substring search, plain `store_tags ILIKE '%tag%'` works.

**Engagement tracking**: `master.total_link_clicks` and `master.total_coupon_copies` are the LIVE counters incremented by the bot + API (`increment_link_clicks` / `increment_coupon_copies`). ⚠️ The columns `link_clicks`, `copy_clicks`, `click_count`, `total_clicks` are LEGACY/stale duplicates (out of sync with the live counters) and are NOT read by any live code — do not use them. Individual events go to `action_logs` with `action_type` (search / click_link / copy_coupon / view_*) and `action_time`.

## Key Tables

| Table | Purpose |
|---|---|
| `master` | All store data: affiliate links, coupons, tags, dates, live counters, trending flag |
| `bot_users` | Telegram user profiles — location, favorites |
| `web_users` | Website account profiles (Firebase OTP auth) |
| `action_logs` | Per-event log for every user interaction |
| `web_visits` | Web session-level tracking (migration_060/061) — separate from action_logs, bot-filtered |
| `direct_search` | Search keyword log with `user_found` boolean (used for gap analysis) |
| `broadcast_logs` / `broadcast_tracking` | Mass Telegram messages + per-user delivery state |
| `user_favorites` | SSOT for favorites across bot + miniapp + web |
| `support_tickets` | Web/bot/API support flow (migration_039) |
| `unavailable_codes_requests` | Requests for stores not yet in the system |
| `seasonal_events` | Calendar events driving the occasions radar feature |
| `security_blacklist` / `security_threats` | Cyber Shield protection tables |
| `story_slides` / `story_media` | Store stories system (video + poster + expiry) |
| `affiliate_conversions` | Admitad postback attribution (migration_064) |
| `seo_*` | SEO auto-pipeline: landing_pages, opportunity_keywords, occasions, perf_snapshots, index_queue |

**Dropped in migration_049** (do not reference): `channel_ads_queue`, `flash_offers_queue`, `franchise_agents`, `loyalty_history`, `loyalty_settings`, `search_analytics`, `app_monitor`, `traffic_sources`, `user_preferences`.

## Trend System

`master.is_trending` holds either `'عادي'` (normal) or `'ترند 🔥'` (trending — emoji-in-data). The dashboard sorts the coupon view so trending stores appear first. Auto-computation uses **`total_link_clicks + total_coupon_copies`** (the LIVE counters).

**⚠️ Type debt (blocked by bot freeze):** `is_trending` should be enum/boolean, and `priority_score` (currently TEXT holding `{'عادي','مهم'}`) should be numeric — but the frozen bot compares them by string, so both changes are held. See `db_foundation_audit.md`.

## Arabic Localization Note

All user-facing text (dashboard labels, bot messages, column renames) is in Arabic. SQL column aliases and table names must remain in English — Arabic identifiers inside SQL cause syntax errors in PostgreSQL. The pattern used everywhere is: query with English column names, then rename DataFrame columns to Arabic in Python before display.
