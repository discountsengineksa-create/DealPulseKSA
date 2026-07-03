---
name: store-analytics-bi-suite-local-groq-constraint
description: How the redesigned «تحليل المتاجر» dashboard section works and why its AI tab calls Groq via REST (not the openai SDK)
metadata: 
  node_type: memory
  type: project
  originSessionId: 50ecd81f-3bcc-44be-81e5-cdb876237262
---

The «تحليل المتاجر» page in `dashboard.py` was rebuilt (2026-05-23) into a 4-sub-tab BI suite:
1. الأداء العام — KPI cards + main smart table (logo via `st.column_config.ImageColumn`, WoW growth colored via pandas Styler) + folded-in trend management.
2. سلوك المستخدمين والترند — peak-hours line, day×hour heatmap, device pie + geo bar (device/city come from `bot_users`, joined `action_logs.user_id = bot_users.telegram_id`).
3. ذكاء الأعمال — rule-based risers/decliners/inactive signals + on-demand Groq consulting report.
4. تقارير المعلنين — store/date filters + CSV and branded xlsxwriter Excel export.

Shared module-level helpers live just after `kpi_card`: `_sa_load_actions`/`_sa_load_master` (cached `@st.cache_data(ttl=180)`), `_sa_pct/_sa_wow/_sa_growth_color/_sa_fmt_growth`, `_sa_groq_report`, `_sa_build_excel`.

**Non-obvious constraints (verify before changing the AI path):**
- The local `venv` does NOT have the `openai` package installed even though `openai==1.55.3` is in requirements.txt. So `_sa_groq_report` calls Groq's OpenAI-compatible endpoint directly via `requests` (POST `https://api.groq.com/openai/v1/chat/completions`), reading `GROQ_API_KEY` / `GROQ_MODEL` from the local `.env` (these lines were appended; key must be pasted — same value as production).
- `action_logs.action_time` is written with `NOW()` on Railway (UTC). Riyadh = UTC+3, applied via constant `RIYADH_TZ_OFFSET_HOURS = 3` for peak-hours/heatmap.
- Engagement Rate = (clicks+copies)/total ; Copy Conversion = copies/clicks ; WoW growth = last 7d vs prior 7d (NaN when prior=0 → shown as "🆕 جديد").

**Data source / quality (critical — added after user said "readings aren't real"):**
- `action_logs` has a `source` column: `'web'` vs `'bot'` (Telegram). Web events are inserted by `api/routers/track.py` via `/api/v1/track/event`. It ALSO has geo/quality columns from migration_010: `device_class` (web: desktop/mobile/tablet/**bot**=crawler), `is_datacenter`, `is_proxy`, `quality_score`, `city`, `country_code`, `cf_bot_score`. Telegram-source rows leave these NULL.
- The store-analysis page now: (a) a "🧹 ترافيك حقيقي فقط" toggle (default ON) filtering `is_genuine = NOT(device_class=='bot' OR is_datacenter OR is_proxy)`; (b) a transparent source/exclusion caption; (c) a dedicated "🌐 الويب" tab (source='web' only) using action_logs' native geo + `web_users` count.
- Real snapshot: 89 key events = 52 telegram + 37 web; **17 of 37 web events were crawlers** (device_class='bot'). Display label everywhere = `store_id` (Arabic); `name_en` is mostly NULL/English — do NOT use it for display.
- Each KPI/signal card stays visible as a card row, with a tab bar BELOW it to drill into each card's details (user's explicit layout). Cards are NOT replaced by tabs.

Verified against real data via smoke tests (peak hour 21:00 Riyadh; genuine filter drops clicks 52→37, copies 17→15). See [[project_overview]].
