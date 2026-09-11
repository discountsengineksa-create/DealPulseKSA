---
name: db-foundation-audit-cleanup-debt
description: "Deep audit of the Postgres schema (2026-06-10) — dead columns/tables, type debt, what's safe vs deferred"
metadata: 
  node_type: memory
  type: project
  originSessionId: c68f1e02-f8e3-449a-b56a-5cb4bf29185a
originSessionId: b6ba939a-2469-4f6a-9833-5d2da06c5e04
---
Deep audit of the production Railway Postgres (2026-06-10/11). At that time the DB had grown to ~76 tables, ~42% empty.

---

## 📌 لقطة حيّة مُتحقَّقة — ٢٠٢٦-٠٨-٠٥

> **كل الأرقام أدناه عُدَّت باستعلام، لا من الذاكرة.** الأرقام القديمة في هذا الملف كانت
> بايتة، و`CLAUDE.md` كان يحمل رقماً ثالثاً مختلفاً (`~67`). ثلاثة مصادر، ثلاثة أرقام،
> والحقيقة على بُعد استعلام واحد. **أعد العدّ قبل أي اقتباس.**

| الحقيقة | القيمة الحيّة | ما كان موثّقاً (غلط) |
|---|---|---|
| جداول الإنتاج | **٧١** | `~67` (CLAUDE.md) / `~76` (هنا) |
| جداول فارغة | **٣٨ = ٥٤٪** | `~42%` |
| صفوف `master` | **٥٢** | `45 stores` |
| `dashboard.py` | **١٥٬٨٦٧ سطر / ١٢٠ دالة / ٣٦ صفحة** | `12,656 / 100 / 32` |
| `bot_users` / `web_users` | **٥ / ١٠** | يطابق [[owned_audience_reality]] ✅ |

**الفارغة (٣٨):** affiliate_conversions, ai_alerts, ai_experiment_events, api_partners,
audience_segment_versions, audience_segments, auto_rules, available_channels,
bot_dynamic_buttons, broadcast_email_opens, broadcast_exclusions, broadcast_link_clicks,
broadcast_link_targets, broadcast_logs, broadcast_recipients, broadcast_schedules,
competitor_watch, content_studio_logs, email_logs, invoice_verifications,
llm_semantic_cache_v2, password_reset_tokens, prediction_logs, product_comparisons,
season_reminders, security_blacklist, security_settings, security_threats,
seo_keyword_blocklist, seo_opportunity_keywords, social_listening_terms, social_responses,
social_signals, story_slides, support_tickets, trend_overrides,
unavailable_codes_requests, user_favorites.

**الأكبر:** api_request_metrics ٢٨٬٧٥٣ · web_visits ٥٬١٢١ · llm_call_log ٨٦٣ ·
action_logs ٧٥٠ · social_posts_log ٥٧٨ · seo_index_submissions ٥٣١.

**✅ شذوذ المفضّلة — حُسم بالكود (٢٠٢٦-٠٨-٠٥):** بدا أن `user_favorites` فارغ
**و**`bot_users.manual_favorites` فارغ بينما `action_logs` يحمل حدث `favorite_add` واحداً
(٢٠٢٦-٠٦-٢٤). التفسير: `deal_pulse_bot.py:2220` يسجّل الإضافة (سطر 2233) **ولا يسجّل الإزالة**
(سطر 2228 يستدعي `_remove_favorite_db` بلا `log_action`). فأُضيف ثم أُزيل، والإزالة غير مرئية.
**الكتابة المزدوجة سليمة** — ثغرة تسجيل لا ثغرة بيانات. التفصيل في [[unified_favorites]].

**أمر إعادة العدّ:**
```python
select count(*) from information_schema.tables
where table_schema='public' and table_type='BASE TABLE';
```

---

**migration_049 (applied to prod 2026-06-11 by user):** dropped 9 tables the user abandoned or that were dead/superseded: channel_ads_queue, flash_offers_queue, franchise_agents, loyalty_history, loyalty_settings (abandoned features); search_analytics (←direct_search), app_monitor (←api_request_metrics), traffic_sources, user_preferences (dead/superseded). All were 0 rows, no FK-in, no view dep, no code refs. DB now ~67 tables. **EXCLUDED `llm_semantic_cache`** — has a row + 5 code refs (v1 still live; would need its refs migrated to llm_semantic_cache_v2 BEFORE dropping). Remaining empty tables are genuine pending-feature scaffolding (security_*, seo_landing_pages, site_themes, broadcast/audience extras, ai_alerts, competitor_watch, product_comparisons, auto_rules, available_channels, bot_dynamic_buttons, content_studio_logs, prediction_logs, api_partners, invoice_verifications) — KEEP unless user says abandoned.

**Done (safe):** `ANALYZE` run (stats were stale on many tables); fixed the AI-assistant prompt in dashboard.py (was teaching the LLM the stale counter columns) → now `total_*`; corrected CLAUDE.md counter docs + table count. Commit a101d71.

**Counter truth (CLAUDE.md was WRONG):** the LIVE counters are `master.total_link_clicks` + `master.total_coupon_copies` (incremented by bot/API). The columns `link_clicks`, `copy_clicks`, `click_count`, `total_clicks` are LEGACY/stale (proven out of sync: 18/20 rows differ) and read by NO live query. `total_search_hits`, `performance_status`, `visit_categorie`, `target_category` also dead (only in tests/setup_test_db.py). KEEP `my_coupon` (live — affiliate tracking code, used in master input/edit + store_extra_coupons).

**DONE (migration_048, applied to prod 2026-06-10 by user):** dropped the dead view `coupons_view` (SELECT…FROM master, zero code refs), dropped 8 dead master columns (link_clicks, copy_clicks, click_count, total_clicks, total_search_hits, performance_status, visit_categorie, target_category), dropped empty unused table `users_master`. Their data preserved in `_deprecated_master_cols_bak_20260610`. master is now 28 clean columns. Gotcha hit during apply: `coupons_view` depended on 5 of the columns (DB-level dep not visible in code grep) → had to DROP VIEW first; ALWAYS check `pg_depend` for views before dropping master columns. The other view `v_social_leads` is unaffected. migration_048 is idempotent/re-run-safe.

**Type debt — EXPAND phase only; NOT resolved (verified live 2026-08-05: all four columns `is_trending`, `is_trending_bool`, `priority_score`, `priority_score_int` still exist in prod):**
- Added `master.is_trending_bool BOOLEAN` and `master.priority_score_int SMALLINT`, backfilled from text columns.
- Text mapping was WRONG in memory: `priority_score` actually has **4 levels** (`'عادي','مهم','عاجل','عاجل جداً'`) not 2. The old TEXT `ORDER BY DESC` silently ranked `'مهم'` (م=U+0645) above `'عاجل جداً'` (ع=U+0639) — a semantic bug now fixed by the int mapping (10 > 6 > 3 > 0).
- All code (bot + dashboard + api + web + miniapp + tests) switched to the new columns in the same commit; old TEXT columns kept for one contract cycle.
- ⚠️ **Contract phase NEVER SHIPPED.** `migration_066` turned out to be *admin flag + analytics hygiene*, not the contract. **No migration in the repo drops the TEXT columns.** Verified 2026-08-05. Consequence: **every write must set both the text and the typed column** until a real contract migration exists.
- **Live discovery from apply:** at the time, all stores in prod were `is_trending=FALSE` / `priority_score_int=0` — the trend/priority feature was coded but unused in production data. (Store count then was quoted as 45; live count is now **52** — re-check the trend flags before acting on this.)

**Relational integrity:** FKs exist only on the web side (31 FKs → master.id / web_users.id). Bot/engagement core has NO FKs → orphans: 85 action_logs.user_id not in bot_users, 3 action_logs + 1 favorite → deleted store. store_id (text) is the cross-table join key but unconstrained everywhere.

**Dashboard ([[store_analytics_bi]]):** dashboard.py = **15,867 lines, 120 funcs, 36 pages** (re-counted 2026-08-05; the audit-day figures 12,656/100/32 are stale) in one if/elif. Auth solid (bcrypt + env/secrets, fails closed). Conn pool maxconn=10 + `_PooledConn` (`__del__` safety net). SQL injection safe (60/62 parameterized; 2 f-strings use column whitelist). Minor: set explicit `DASHBOARD_COOKIE_KEY` (fallback = sha256(password)).
