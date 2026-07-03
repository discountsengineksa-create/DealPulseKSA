---
name: db-foundation-audit-cleanup-debt
description: "Deep audit of the Postgres schema (2026-06-10) — dead columns/tables, type debt, what's safe vs deferred"
metadata: 
  node_type: memory
  type: project
  originSessionId: c68f1e02-f8e3-449a-b56a-5cb4bf29185a
---

Deep audit of the production Railway Postgres (2026-06-10/11). The DB had grown to ~76 tables, ~42% empty.

**migration_049 (applied to prod 2026-06-11 by user):** dropped 9 tables the user abandoned or that were dead/superseded: channel_ads_queue, flash_offers_queue, franchise_agents, loyalty_history, loyalty_settings (abandoned features); search_analytics (←direct_search), app_monitor (←api_request_metrics), traffic_sources, user_preferences (dead/superseded). All were 0 rows, no FK-in, no view dep, no code refs. DB now ~67 tables. **EXCLUDED `llm_semantic_cache`** — has a row + 5 code refs (v1 still live; would need its refs migrated to llm_semantic_cache_v2 BEFORE dropping). Remaining empty tables are genuine pending-feature scaffolding (security_*, seo_landing_pages, site_themes, broadcast/audience extras, ai_alerts, competitor_watch, product_comparisons, auto_rules, available_channels, bot_dynamic_buttons, content_studio_logs, prediction_logs, api_partners, invoice_verifications) — KEEP unless user says abandoned.

**Done (safe):** `ANALYZE` run (stats were stale on many tables); fixed the AI-assistant prompt in dashboard.py (was teaching the LLM the stale counter columns) → now `total_*`; corrected CLAUDE.md counter docs + table count. Commit a101d71.

**Counter truth (CLAUDE.md was WRONG):** the LIVE counters are `master.total_link_clicks` + `master.total_coupon_copies` (incremented by bot/API). The columns `link_clicks`, `copy_clicks`, `click_count`, `total_clicks` are LEGACY/stale (proven out of sync: 18/20 rows differ) and read by NO live query. `total_search_hits`, `performance_status`, `visit_categorie`, `target_category` also dead (only in tests/setup_test_db.py). KEEP `my_coupon` (live — affiliate tracking code, used in master input/edit + store_extra_coupons).

**DONE (migration_048, applied to prod 2026-06-10 by user):** dropped the dead view `coupons_view` (SELECT…FROM master, zero code refs), dropped 8 dead master columns (link_clicks, copy_clicks, click_count, total_clicks, total_search_hits, performance_status, visit_categorie, target_category), dropped empty unused table `users_master`. Their data preserved in `_deprecated_master_cols_bak_20260610`. master is now 28 clean columns. Gotcha hit during apply: `coupons_view` depended on 5 of the columns (DB-level dep not visible in code grep) → had to DROP VIEW first; ALWAYS check `pg_depend` for views before dropping master columns. The other view `v_social_leads` is unaffected. migration_048 is idempotent/re-run-safe.

**Type debt — BLOCKED by bot freeze ([[bot-frozen-lock]]):**
- `is_trending` is varchar holding the display string `'عادي'`/`'ترند 🔥'` (emoji-in-data). Changing to boolean/enum breaks the frozen bot's `=== 'ترند 🔥'` comparisons (and API/web). Needs bot unfreeze + coordinated change.
- `priority_score` is TEXT holding `{'عادي','مهم'}`; bot does `ORDER BY priority_score DESC` — works only by lexical accident (م>ع). Needs numeric/enum + bot change.

**Relational integrity:** FKs exist only on the web side (31 FKs → master.id / web_users.id). Bot/engagement core has NO FKs → orphans: 85 action_logs.user_id not in bot_users, 3 action_logs + 1 favorite → deleted store. store_id (text) is the cross-table join key but unconstrained everywhere.

**Dashboard ([[store_analytics_bi]]):** dashboard.py = 12,656 lines, 100 funcs, 32 pages in one if/elif. Auth solid (bcrypt + env/secrets, fails closed). Conn pool maxconn=10 + `_PooledConn` (`__del__` safety net). SQL injection safe (60/62 parameterized; 2 f-strings use column whitelist). Minor: set explicit `DASHBOARD_COOKIE_KEY` (fallback = sha256(password)).
