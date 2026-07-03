---
name: Local Setup Guide — New Machine
description: Step-by-step to run DealPulse KSA on a new machine from scratch
type: project
originSessionId: 3eb16deb-09fb-42ac-aa86-1b1afa492099
---
## Setup on a New Machine

### 1. Prerequisites
- Python 3.11+ (python.org)
- PostgreSQL 15+ (postgresql.org) — create DB `discounts_engine`, user `postgres`, pass `123456`
- Git

### 2. Clone & Install

```bash
git clone https://github.com/discountsengineksa-create/DealPulseKSA.git
cd DealPulseKSA
pip install -r requirements.txt
```

### 3. Copy Secret Files (from flash drive — NOT in git)

```
.env                        → project root
.streamlit/secrets.toml     → .streamlit/ folder
```

### 4. Run Migrations (first time only)

Run these SQL files in order on the local DB using pgAdmin or psql:

```
migration_001_action_logs_user_id.sql
migration_002_web_support.sql
migration_003_auth.sql
migration_004_auth_fix.sql
migration_005_bilingual.sql
migration_006_logo.sql
migration_007_email_logs.sql
```

Or if you have `db_export.sql` (full dump), restore it instead:
```bash
psql -U postgres -d discounts_engine < db_export.sql
```

### 5. Start Services

```bash
# Terminal 1 — Dashboard
streamlit run dashboard.py

# Terminal 2 — Bot
python deal_pulse_bot.py

# Terminal 3 — API (optional, for website integration)
uvicorn api.main:app --reload --port 8000
```

---

## Required .env Variables

```env
BOT_TOKEN=                    # من BotFather
DATABASE_URL=                 # Railway URL (للإنتاج فقط)
DB_NAME=discounts_engine      # محلي
DB_USER=postgres
DB_PASSWORD=123456
DB_HOST=localhost
DB_PORT=5432
JWT_SECRET=                   # openssl rand -base64 64
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
RESEND_API_KEY=               # من resend.com
SMTP_FROM=noreply@dealpulseksa.com
SMTP_FROM_NAME=نبض الصفقات
IDLE_WARN_MINUTES=5
IDLE_KICK_MINUTES=10
```

## .streamlit/secrets.toml Structure

```toml
[auth]
cookie_name = "deal_pulse_admin"
cookie_key  = "<random 64-char string>"
cookie_expiry_days = 1

[auth.credentials.usernames.admin]
name     = "Admin"
email    = "admin@dealpulse.local"
password = "<bcrypt hash>"
```

Generate bcrypt hash:
```python
import bcrypt
print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())
```
