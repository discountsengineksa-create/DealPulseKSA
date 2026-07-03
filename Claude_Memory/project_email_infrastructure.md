---
name: Email Infrastructure Setup
description: Resend API integrated with dealpulseksa.com domain for sending emails
type: project
---

Resend API is fully configured for the project.

**Why:** User set up Resend account, verified dealpulseksa.com domain via Cloudflare auto-configure.

**How to apply:** Use RESEND_API_KEY env var. Sender is noreply@dealpulseksa.com. Both local .env and Railway Variables have the key. The _send_campaign_email() function in dashboard.py and send_reset_email() in api/auth_utils.py use Resend as primary, SMTP as fallback.
