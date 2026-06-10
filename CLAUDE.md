# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

Database credentials are in `.env` and must match the hardcoded values in `deal_pulse_bot.py` — keep both in sync.

## Architecture

Three components share one PostgreSQL database (`discounts_engine` on localhost:5432):

- **`dashboard.py`** — Streamlit admin interface. A single 2800+ line file; all 32 pages are implemented as one long `if/elif` chain keyed on `page = st.sidebar.radio(...)`. No page routing abstraction.
- **`deal_pulse_bot.py`** — Telegram bot using `pyTelegramBotAPI` (`telebot`). Exposes the coupon catalog to end-users via Arabic keyboard buttons and inline cards.
- **PostgreSQL** (Railway prod, via `DATABASE_URL`) — ~76 tables (grew well beyond the original 31; ~40% are empty/dormant pending-feature tables). The `master` table is the source of truth for all store/coupon data.

## Database Patterns

**Connection helper** used throughout both files:
```python
def get_conn():
    return psycopg2.connect(dbname="discounts_engine", user="postgres", password="123456", host="localhost", port="5432")
```

**Always open and close connections per request** — connections are not pooled or reused across Streamlit reruns.

**Transaction state**: Pages that only read data still call `conn.rollback()` (or `conn.autocommit = True`) at the top to clear any aborted-transaction state left from a previous error. This is a deliberate recurring pattern — do not remove it.

**`store_tags` column** is declared as plain `text` (NOT `text[]`), but data is written in PostgreSQL array-literal format `'{tag1,tag2,tag3}'`. Calls like `unnest(store_tags)`, `array_to_string(store_tags, ',')`, or `%s = ANY(store_tags)` will fail at runtime — the column is text, the operator expects array. To work with it in SQL, convert first: `string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',')`. For substring search, plain `store_tags ILIKE '%tag%'` works.

**Engagement tracking**: `master.total_link_clicks` and `master.total_coupon_copies` are the LIVE counters incremented by the bot + API (`increment_link_clicks` / `increment_coupon_copies`). ⚠️ The columns `link_clicks`, `copy_clicks`, `click_count`, `total_clicks` are LEGACY/stale duplicates (out of sync with the live counters) and are NOT read by any live code — do not use them. Individual events go to `action_logs` with `action_type` (search / click_link / copy_coupon / view_*) and `action_time`.

## Key Tables

| Table | Purpose |
|---|---|
| `master` | All store data: affiliate links, coupons, tags, dates, click counters, trending flag |
| `bot_users` | Telegram user profiles — behavioral inference, location, favorites, loyalty rank |
| `action_logs` | Per-event log for every user interaction |
| `direct_search` | Search keyword log with `user_found` boolean (used for gap analysis) |
| `broadcast_logs` | History of mass Telegram messages |
| `unavailable_codes_requests` | Requests for stores not yet in the system |
| `seasonal_events` | Calendar events driving the occasions radar feature |
| `security_blacklist` / `security_threats` | Cyber Shield protection tables |
| `channel_ads_queue` | Scheduled posts for the channel publisher feature |
| `flash_offers_queue` | Time-limited reward offers |
| `user_loyalty` / `loyalty_history` | Points and rank management |

## Trend System

`master.is_trending` holds either `'عادي'` (normal) or `'ترند 🔥'` (trending). The dashboard sorts the coupon view so trending stores appear first. Trending status can be set manually per store or computed automatically from `copy_clicks + link_clicks`.

## Arabic Localization Note

All user-facing text (dashboard labels, bot messages, column renames) is in Arabic. SQL column aliases and table names must remain in English — Arabic identifiers inside SQL cause syntax errors in PostgreSQL. The pattern used everywhere is: query with English column names, then rename DataFrame columns to Arabic in Python before display.
