---
name: Contact Emails
description: Two distinct email addresses — personal vs brand ops mailbox — and which one to use where
type: reference
originSessionId: 2365933b-99f5-4d83-8946-8881709c88f5
---
The project has TWO email addresses; they are NOT interchangeable.

| Purpose | Address | Where it's used |
|---|---|---|
| Personal (Claude system identifier) | `90yosh@gmail.com` | Reference only — DO NOT default to this for any product feature |
| Brand ops mailbox | `dealpulesksa@gmail.com` | All operational alerts: Financial Guardian breaches, spike alerts, AI directives, system failures |

**Why this matters:** The user corrected me on 2026-05-21 after I defaulted `OPS_ALERT_EMAIL` to the personal address. Brand ops mail goes to the dedicated mailbox so the personal inbox stays clean.

**Spelling note:** It's `dealpules` (without the "e" before "k") — not `dealpulse`. The brand name in code/UI is "Deal Pulse KSA" but the email is spelled `dealpulesksa@gmail.com`. Don't auto-correct it.

**Where this default is enforced:**
- `.env.example` → `OPS_ALERT_EMAIL=dealpulesksa@gmail.com`
- `api/utils/email_alerts.py` → `OPS_EMAIL = os.getenv("OPS_ALERT_EMAIL", "dealpulesksa@gmail.com")`
