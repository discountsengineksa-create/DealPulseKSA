---
name: Contact Emails
description: The real brand mailbox is dealpulseksa@gmail.com (pulse); dealpulesksa (pules) is a typo bug in code
type: reference
originSessionId: 2365933b-99f5-4d83-8946-8881709c88f5
---
The project's emails — do NOT mix them up.

| Purpose | Address | Notes |
|---|---|---|
| **Brand ops / public mailbox** | **`dealpulseksa@gmail.com`** (spelling = `dealpulse`, same as the domain) | ✅ The REAL mailbox. Use for all ops alerts + public contact. |
| Personal (Claude system identifier) | `90yosh@gmail.com` | Reference only — never a product default. |
| DCM Network publisher login | `discountsengineksa@gmail.com` | Login + approval/rejection notifications for the DCM affiliate account (Id 166846). A separate third inbox — watch it for [[boostiny_publisher_channel]] approvals. |

**✅ RESOLVED 2026-07-20 (owner confirmed twice — also 2026-07-04):** the real brand mailbox is **`dealpulseksa@gmail.com`** (pulse). The spelling `dealpulesksa@gmail.com` (**pules**, no "e" before the k) is a **typo / NOT a real inbox** — my earlier memory had it backwards. It matches: owner's `web_users` account (`migration_066`), the backup workflows (`db-backup.yml`), and the live site (`lib/seo/constants.ts`). See resolved conflict in [[seo_authority_building]] and [[domain_canonical_trap]] (same pulse-vs-pules trap as the domain).

**🐛 CODE BUG (pending fix):** the wrong `pules` spelling is still hard-coded as the ops-alert default in:
- `.env.example:101` → `OPS_ALERT_EMAIL=dealpulesksa@gmail.com`
- `api/utils/email_alerts.py:16` → `OPS_EMAIL = os.getenv("OPS_ALERT_EMAIL", "dealpulesksa@gmail.com")`

→ Ops alerts (Financial Guardian, spike, failures) route to a dead address unless Railway's `OPS_ALERT_EMAIL` env overrides it. Fix both to `dealpulseksa@gmail.com`, and check the Railway env var too.
