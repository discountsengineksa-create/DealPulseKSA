---
name: Project Overview — DealPulse KSA
description: Architecture, DB, deployment, and key file locations for the DealPulse KSA discounts engine
type: project
originSessionId: 3eb16deb-09fb-42ac-aa86-1b1afa492099
---
## Project: نبض الصفقات — DealPulse KSA

**GitHub:** https://github.com/discountsengineksa-create/DealPulseKSA  
**Production:** Railway (API + Bot as separate services)  
**Website:** https://dealpulseksa.com (Next.js, separate repo at C:\Users\PC\Desktop\dealpulseksa-web)

---

## 3 Components, 1 PostgreSQL Database

| Component | File | Run Command | Port |
|---|---|---|---|
| Admin Dashboard | `dashboard.py` | `streamlit run dashboard.py` | 8501 |
| Telegram Bot | `deal_pulse_bot.py` | `python deal_pulse_bot.py` | — |
| REST API | `api/main.py` | `uvicorn api.main:app --reload --port 8000` | 8000 |

---

## Database

- **Local:** `discounts_engine` on `localhost:5432`, user `postgres`, pass `123456`
- **Production Railway:** `turntable.proxy.rlwy.net:18475` (DATABASE_URL in .env)
- **Key tables:** `master` (coupons), `bot_users` (Telegram users), `web_users` (website users), `action_logs`, `direct_search`, `email_logs`, `broadcast_logs`, `flash_offers_queue`, `sent_coupon_messages`

### store_tags gotcha
`store_tags` is `TEXT` not `TEXT[]`. Written as `'{tag1,tag2}'`. Use:
```sql
string_to_array(trim(both '{}' from COALESCE(store_tags, '')), ',')
```
Never `unnest(store_tags)` directly — it crashes.

---

## Connection Pattern (Dashboard)

```python
conn = get_conn()
# ... use conn ...
conn.close()  # returns to pool, not real close
```

`_PooledConn` has `__del__` as safety net — if exception skips `close()`, GC returns to pool automatically. Also supports `with get_conn() as conn:` (auto commit/rollback).

---

## Bot Architecture

- **Polling mode** locally (`RUN_MODE=polling`)
- **Two-stage idle:** warn at 5min (`IDLE_WARN_MINUTES`), kick at 10min (`IDLE_KICK_MINUTES`)
- **Connection pool:** `ThreadedConnectionPool` min=2 max=8
- **i18n:** `TEXTS` dict with `ar`/`en` keys, `get_lang(user_id)` has 5-min TTL cache
- **Navigation:** single "nav message" per user edited in-place (no message spam)

---

## API Endpoints

```
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
POST /api/v1/auth/forgot-password
POST /api/v1/auth/reset-password
GET  /api/v1/coupons/search
GET  /api/v1/coupons/categories
POST /api/v1/track/event
GET  /health
GET  /miniapp  (Telegram Mini App HTML)
```

---

## External Services

| Service | Purpose | Key location |
|---|---|---|
| Cloudinary | Store logos upload/serve | `CLOUDINARY_*` in .env |
| Resend API | Password reset emails | `RESEND_API_KEY` in .env |
| Railway | Production hosting | railway.app dashboard |
| Telegram BotFather | Bot token | `BOT_TOKEN` in .env |

---

## Files NOT in Git (must copy manually)

1. `.env` — all API keys + DB credentials
2. `.streamlit/secrets.toml` — Streamlit admin login (bcrypt hash)

**Why:** Both are in `.gitignore` for security.
