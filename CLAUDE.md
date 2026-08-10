# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 🧠 **READ FIRST, EVERY SESSION: [`AGENT_PLAYBOOK.md`](AGENT_PLAYBOOK.md).** It is
> the working method the owner expects — diagnose root cause not symptoms, verify
> end-to-end, be honest about ceilings, and keep the shared `Claude_Memory/` up to
> date. The difference between solving a problem in one pass vs. failing six times
> is that playbook, not raw intelligence. Also read `Claude_Memory/MEMORY.md` (the
> memory index) and open any entry relevant to your task before touching code.

---

# 🧱 الحوائط الصلبة — نصّاً، لا بالإحالة

> هذه القواعد كانت تعيش كملفات في `Claude_Memory/`. **الفهرس يُحمَّل، المتون لا** —
> فكان الحائط يعتمد على أن أفتح ملفاً، وأحياناً لا أفتحه. مكتوبة هنا لأن هذا الملف
> يُحمَّل بالكامل في كل جلسة. مخالفة أيٍّ منها = ضرر حقيقي، لا مجرّد أسلوب.

| # | الحائط | التفصيل |
|---|---|---|
| ١ | **لا كتابة DB بلا إذن صريح للعملية** | `INSERT/UPDATE/DELETE/ALTER/DROP` على الإنتاج يحتاج إذناً لتلك العملية بعينها. **«يلا نبدأ» ليس إذناً.** القراءة مسموحة. → `feedback_no_db_writes_without_permission.md` |
| ٢ | **`main` = إنتاج Railway** | الدفع إلى `main` ينشر فوراً. اتبع بروتوكول ما قبل الدفع في `AGENT_PLAYBOOK.md` §٤.٩. لا دفع تجريبي. |
| ٣ | **صفر فبركة** | كل رقم في أي تقرير يُعَدّ حيّاً بأمر. «~» أو «حوالي» = علم أحمر: عُدَّه أو احذفه. الاستشهاد بملف/سطر حرفياً. ادّعاء رقم من الذاكرة بدل عدّه = تلفيق. |
| ٤ | **White-Hat فقط** | لا doorway، لا صفحات رقيقة مكرّرة، لا مزايدة مدفوعة على اسم براند. → `seo_white_hat_only.md` + `affiliate_ppc_brand_restrictions.md` |
| ٥ | **لا تنشر كود منافس** | لا يُذكر كود المتجر الترحيبي ولو كان خصمه أعلى. → `feedback_never_publish_competing_codes.md` |
| ٦ | **البوت مفكوك — لكن ضمن البروتوكول** | التعديل مسموح (٢٠٢٦-٠٧-٠٧)، بإعلان → تحقّق → إثبات → تسجيل. تاغ الرجوع `bot-locked-2026-06-10`. |
| ٧ | **انشر عند الإنجاز** | جهازان. عند اكتمال أي شغل: `commit` + `push` بلا سؤال. لا `stash`، لا شغل يبقى محلياً. `pull` في بداية الجلسة. |
| ٨ | **الأكواد قبل روابط التتبّع** | المالك يفضّل الأكواد: إسناد أنظف، والروابط تُحجب ونقرها غير موثوق. |

**أسلوب العمل:** المالك مهندس خبير ٢٠+ سنة. **لا فلسفة، لا قوائم خيارات، لا أساسيات، لا تمهيد.**
اقرأ → حدّد → نفّذ. عند العجز: سؤال نصّي واحد. المخرَج يُقيَّم بنتيجته لا بصعوبة سباكته،
واكشف سقف الأداة بصراحة بدل تجميله. → `feedback_no_philosophy.md` · `feedback_senior_engineer.md` · `feedback_output_over_engineering.md`

### 🔑 طقس بداية المهمة (إلزامي)

قبل أي تنفيذ، **أعلن أسماء ملفات الذاكرة التي فتحتها فعلاً** لهذه المهمة.
لم تُعلن = لم تقرأ، وللمالك أن يوقفك فوراً. الفهرس يعطي العناوين فقط —
**العنوان ليس الحقيقة، المتن هو الحقيقة.**

---

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

`run_all.py` starts the bot and the dashboard together as two subprocesses (Ctrl+C terminates both) — a convenience wrapper around the two commands above, not a separate entrypoint.

## Testing

```bash
# All tests
pytest tests/ -v

# One file / one test
pytest tests/test_auth.py -v
pytest tests/test_auth.py::test_register_success -v
```

⚠️ `pytest.ini` declares markers `slow` / `requires_db` / `requires_llm`, but **no test carries any marker** (zero `@pytest.mark.` in `tests/`), so `-m "not slow"` filters nothing and runs the whole suite. DB-dependent tests skip themselves through the `db_available` fixture instead — there is no marker-based way to select them.

Tests need `TEST_DATABASE_URL` (a separate Railway Postgres instance with migrations applied — **never point this at prod**), plus `JWT_SECRET` and `ADMIN_SHARED_SECRET`; `conftest.py` fixture `db_available` auto-skips DB-dependent tests when `TEST_DATABASE_URL` isn't set. Full setup steps (provisioning the test DB, applying migrations, `tests/.env.test` template) are in `tests/README.md`. 25 tests cover auth, JWT, `track`/`go` routers, LLM cache, and the Financial Guardian — no lint/type-check tooling is configured in this repo.

## Architecture

Four runnable entrypoints share one PostgreSQL database:

- **`dashboard.py`** — Streamlit admin interface. A single **16,104-line** file; all **37 pages** are implemented as one long `if/elif` chain. **Page routing** (`dashboard.py:1878-1900`): three grouped lists — `_MAIN_PAGES` (12), `_ANALYSIS_PAGES` (8), `_OTHER_PAGES` (17) — rendered as sidebar expanders with `st.radio` + `handle_nav`, driving `st.session_state.page`. ⚠️ The `st.sidebar.radio(...)` at `dashboard.py:1871` is the **theme toggle**, not the page selector — don't confuse them. **⚠️ `main = production Railway` — see `AGENT_PLAYBOOK.md` §4.9 for the pre-push safety protocol.**
- **`deal_pulse_bot.py`** — Telegram bot (~2,376 lines) using `pyTelegramBotAPI` (`telebot`). **🔓 Freeze LIFTED 2026-07-07** — edits allowed under the partnership protocol (declare → verify → prove → record). Rollback tag: `bot-locked-2026-06-10`. See `Claude_Memory/bot_frozen_lock.md`. Lifting the freeze does **not** waive the DB-write wall or the `main=prod` wall.
- **`bot_app.py`** — Production Railway entrypoint (~418 lines). Combines bot + FastAPI (**12 routers** — counted 2026-08-05 via `include_router`; the "11" previously documented here was wrong) + Mini App into one service. Routers: admin, auth, broadcast_tracking, contact, coupons, go, reminders, seo, social, track, trend, users.
- **`api/main.py`** — API-only entrypoint for local dev (`uvicorn api.main:app --port 8000`). Production runs `bot_app.py` instead.
- **PostgreSQL** (Railway prod, via `DATABASE_URL`) — migrations run to **`migration_069`** (67 migration files in repo root). **Counted live 2026-08-05: 71 base tables, 38 of them empty (54%), `master` = 52 rows.** Two previously documented figures were both wrong (`~67` in this file, `~76` in memory) — that is exactly the drift this doc now guards against. **Re-count before quoting; the query is in `Claude_Memory/db_foundation_audit.md`.** Local `discounts_engine` on `localhost:5432` is a dummy/test DB only. The `master` table is the source of truth for all store/coupon data.

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
| `bot_users` | Telegram user profiles — 26 columns. Favorites live in `manual_favorites` (there is **no** `favorites` column); also `fav_store_inferred` / `fav_tag_inferred` |
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

**Type debt — EXPAND phase applied, dual-write is live.** `migration_065_type_debt_expand.sql` (2026-07-07, after the freeze lifted) added `is_trending_bool` BOOLEAN and `priority_score_int` SMALLINT alongside the legacy text columns and backfilled both. The typed columns are used in **35 places across 6 files** (dashboard, bot, `api/routers/coupons.py`, `api/routers/track.py`, `api/utils/llm_service.py`, tests). **No contract migration exists yet** — the legacy TEXT columns `is_trending` / `priority_score` are still present and still read by some paths, so **any write must set both the text and typed column**. Do not drop the text columns without a dedicated contract migration. See `db_foundation_audit.md`.

## Arabic Localization Note

All user-facing text (dashboard labels, bot messages, column renames) is in Arabic. SQL column aliases and table names must remain in English — Arabic identifiers inside SQL cause syntax errors in PostgreSQL. The pattern used everywhere is: query with English column names, then rename DataFrame columns to Arabic in Python before display.
