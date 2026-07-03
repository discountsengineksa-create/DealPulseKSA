---
name: Check local config before suggesting infra changes
description: When user reports a config-related bug (env vars, secrets, API keys, deploy state), read .env / settings files FIRST before asking them to verify on Railway/Vercel/etc.
type: feedback
originSessionId: 2ea6b109-3dfe-4ba0-bf97-1d6265497f70
---
عند الإبلاغ عن مشكلة config (إيميل لا يصل، API key مفقود، deploy لم يُطبَّق…)
ابدأ بقراءة `.env` المحلي + استدعاء أي endpoint تشخيصي موجود قبل أن تطلب من
المستخدم التحقق يدوياً على لوحة Railway/Vercel/Resend.

**Why:** في حالة "نسيت كلمة المرور لا يصل الإيميل" (2026-05-31)، كان
`RESEND_API_KEY` + `SMTP_FROM` + `SMTP_FROM_NAME` كلها موجودة في `.env`
وعلى Railway أصلاً، والدومين موثّق على Resend منذ 19 يوم، والإيميل
`last_event=delivered`. المشكلة الفعلية كانت `last_event=delivered`
لكن المستخدم لم يفحص spam/Promotions folder. أنا طلبت منه يضبط
Railway → Variables من جديد فضيّع ~ساعتين قبل ما نكتشف أن كل شي
مهيّأ. كان ممكن `grep RESEND .env` يحلّ المسألة في 5 ثوان.

**How to apply:**
1. لو المستخدم قال "X لا يعمل / لا يصل":
   - `grep` الـ env var المعنية في `.env` و `.env.example`.
   - استدعِ أي endpoint تشخيصي موجود (مثلاً `/admin/email-status`) قبل
     اقتراح تعديل على production.
   - افحص لوحة الخدمة الخارجية (Resend dashboard, Stripe logs…) لو متاحة.
2. اقترح تعديل Railway/Vercel **فقط بعد** التأكد أن المتغيرات ليست مضبوطة.
3. لو الإيميل يُسلّم بحسب Resend لكن المستخدم لا يراه — وجّهه أولاً لـ
   spam/Promotions قبل تشخيص الـ DNS.

**حالة مختلفة — أسئلة الاتصال الإنتاجي (2026-06-19):**
لو السؤال "هل أنت متصل بـ X الآن؟" أو "هل المنصة الفلانية تعمل في الإنتاج؟"
→ `.env` المحلي **لا يعكس** حالة الإنتاج. غالباً يكون فاضي محلياً ومضبوط على Railway.
- لا تستنتج "غير متصل" من غياب المتغير في `.env` المحلي.
- اطلب من المستخدم لقطة Variables من Railway، **أو** اقترح إضافة endpoint
  تشخيصي مثل `/admin/social-status` يرجّع `{platform: is_configured}` من الـruntime.
- المثال: في `2026-06-19` المستخدم سأل "أنت متصل بـ Instagram API؟"، وقلت "لا"
  بناءً على `.env` فاضي. Railway فيه `IG_BUSINESS_ID` و`META_PAGE_ACCESS_TOKEN` معبّأين
  والناشر مفعّل فعلاً. المستخدم اعتبرها مخالفة لمبدأ التحقق قبل الاستنتاج.
