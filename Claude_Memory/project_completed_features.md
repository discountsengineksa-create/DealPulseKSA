---
name: Completed Features Log
description: Features built and fixed in recent sessions
type: project
---

**Email Marketing Module (dashboard.py مركز الإشعارات):**
- Added st.tabs: تليجرام tab (existing) + البريد الإلكتروني tab (new)
- Email tab: audience filter based on web_users.last_seen, subject/body/banner inputs, newsletter HTML preview via components.html, send via Resend, logs to email_logs table
- email_logs table created on both local and Railway PostgreSQL

**تحليل الموقع fix:**
- Was: single connection for all 5 tabs → one failure killed all
- Now: each tab has its own connection with autocommit=True and isolated try/except

**Forgot Password / Auth fix:**
- auth router was missing from api/main.py — added it (this was the root cause of ConnectionRefused)
- Updated send_reset_email() HTML template: green gradient header, large code box, green CTA button "تعيين كلمة مرور جديدة", 15-min warning

**How to apply:** All backend endpoints are under /api/v1/auth/*. Frontend pages already exist at /forgot-password and /login. Railway deploy needed after git push.
