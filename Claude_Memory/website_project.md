---
name: DealPulseKSA Website Project
description: Next.js website for dealpulseksa.com — repo location, Firebase project, deployment status
type: project
originSessionId: cea0f63e-ba76-4d17-afa2-ac0c9cecc7b9
---
ملف موقع dealpulseksa.com منفصل عن مستودع البوت.

**Why:** الموقع تطبيق Next.js 14 مستقل، يستهلك نفس الـ FastAPI backend اللي يخدم البوت على Railway. الإحصائيات (clicks/copies/searches) موحّدة بين البوت والموقع عبر عمود `source` في `action_logs`.

**How to apply:**
- **مسار المشروع المحلي**: `c:\Users\user\Desktop\dealpulseksa-web\` (مش داخل مستودع Discounts_Engine)
- **GitHub repo**: `discountsengineksa-create/dealpulseksa-web` (private)
- **Firebase project ID**: `dealpulseksa-aab18`
- **Firebase auth method**: Phone OTP فقط (Spark plan, 10 SMS/day limit)
- **API base URL**: `https://dealpulseksa-production.up.railway.app/api/v1`
- **Stack**: Next.js 14.2.15 + TypeScript + Tailwind + Firebase 10 + framer-motion
- **حالة النشر** (آخر تحديث 2026-05-09):
  - ✅ GitHub: مدفوع
  - ✅ Firebase: Phone Auth مفعّل + Authorized domains (localhost, *.firebaseapp.com, *.web.app, dealpulseksa.com, dealpulseksa.vercel.app)
  - ✅ Vercel: منشور (`dealpulseksa-web.vercel.app`)
  - ✅ Cloudflare DNS: مربوط — A record للـ apex + CNAME للـ www يشيرون لـ Vercel، Proxy: DNS only (رمادي)
  - ✅ Custom domains: `dealpulseksa.com` (307 redirect → www) + `www.dealpulseksa.com` (Production) — كلاهما Valid Configuration
- Firebase config (apiKey وغيره) آمنة كـ public — لكن المستخدم يحفظها في Notepad محلياً للصق في Vercel env vars
