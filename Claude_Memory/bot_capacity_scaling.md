---
name: bot-capacity-scaling-roadmap
description: "Telegram bot real-time concurrency ceiling, applied tuning, and the path to scale (user wants"
metadata: 
  node_type: memory
  type: project
  originSessionId: c68f1e02-f8e3-449a-b56a-5cb4bf29185a
---

**Ambition (stated 2026-06-10):** user intends DealPulse to become **#1 in Saudi Arabia, then UAE**. So scaling/capacity is a first-class concern, not an afterthought.

**Architecture reality (bot_app.py):** single process `uvicorn bot_app:app` (no `--workers`), `numReplicas=1`. Webhook → `queue.Queue` → N persistent worker threads call `bot.process_new_updates`. `bot.threaded=False` + custom `exception_handler` (see [[bug_fixes]] #12). State (`_user_nav`, `_lang_cache`, `_cats_cache`) is **in-process memory** → CANNOT add replicas without moving nav state to Redis (a callback could hit a replica with no session).

**The binding ceiling = Telegram, not our code:** Telegram limits a single bot token to **~30 messages/sec** (to different chats). Each interaction does ~1 message-op (editMessage); answerCallbackQuery is lighter/separate. So real-time throughput is capped at **~30 actions/sec per bot token** no matter how fast our code is.

**Capacity framing — it's TAP RATE, not sessions:** the constraint is button-presses processed per second, NOT number of open sessions. Thousands of open sessions = cheap (in-memory dict). A spike of N simultaneous taps drains at ~30/s. Example the user asked about: 7000 present + 2000 tapping "copy نمشي" in the same instant → queue (12000) holds all (no drops, no crash), drains at ~30/s ⇒ tail user waits ~60-70s. Spread over ~60s think-time, 2000 concurrent ≈ ~33/s ≈ fine.

**Applied tuning (commit eff2d6f, 2026-06-10) — target ~2000 concurrent:**
- `_NUM_BOT_WORKERS` 4 → 16 (saturates ~30/s without over-firing → 429s).
- update queue `maxsize` 2000 → 12000 (absorbs bursts; was silently dropping on full).
- bot pool `maxconn` 8 → 20 (16 workers + headroom). NOTE: API pool (api/db.py) is also maxconn=20 in the SAME process ⇒ ~40 conns from unified service; verify Railway Postgres `max_connections` before pushing higher; consider PgBouncer at scale.
- `backfill_user_behavior` removed from every startup (O(users) DB hammer each deploy) → now behind `RUN_BACKFILL=1` one-time only (live `update_user_behavior` maintains stats going forward).

**Path to真 scale (beyond ~30/s real-time) — NOT yet built:**
1. Redis for nav/session state → enables multiple replicas (horizontal).
2. PgBouncer / right-size pools as connections grow.
3. To exceed Telegram's per-token cap for tens-of-thousands simultaneous: **bot-token sharding** (multiple tokens) or accept queued latency. Only needed for genuine 10k+ simultaneous-tap spikes.

Rejected (premature): async analytics ThreadPoolExecutor — DB isn't the ceiling, Telegram is. See [[feedback-no-dead-code]].
