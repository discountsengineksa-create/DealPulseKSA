---
name: users-analytics-rules
description: Canonical counting/identity/geo rules for the rebuilt «تحليل المستخدمين» section
metadata: 
  node_type: memory
  type: project
  originSessionId: 1852a4cb-f634-46c7-bb76-a04947c91d64
---

قواعد ثابتة لقسم «تحليل المستخدمين» الجديد (أقرّها المستخدم 2026-06-05). البناء: تبويبان فقط داخل الصفحة — «التحليل العام» و «التحليل الفردي». التحليل العام فيه فلتر مصدر pills (الكل/بوت/ميني-ويب/موقع) + زر تحديث.

**1) الهوية والإجمالي الموحّد:**
- بوت + ميني-ويب = نفس `bot_users.telegram_id` (شخص واحد، يختلف فقط بنقطة الدخول من `action_logs.source`).
- مستخدم موقع = `web_users` (id، تسجيل إجباري).
- دمج عبر المنصات: لو `LOWER(web_users.telegram_username) = LOWER(bot_users.username)` → نفس الشخص يُعدّ مرة.
- الإجمالي = عدد أشخاص تيليجرام + مستخدمي موقع غير المربوطين.
- العدّ من جداول الهوية (`bot_users`/`web_users`)، لا من `action_logs` (فيه أشباح ما قبل التفعيل + user_id فضاءان مختلفان؛ ممنوع COUNT(DISTINCT user_id) عبر المصادر).

**2) الحركة المعتبرة (للنشاط):** أفعال النية فقط: `search, click_link, copy_coupon, view_*, favorite_*, request_code, reaction_*`. تُستبعد: `idle_warn/idle_alert/idle_kick` (الأغلبية الساحقة ~645)، و`start/end_session/back/unknown_input`.

**3) المدينة/الجغرافيا:** فقط `action_logs.city` (IP حقيقي وقت نقر /go، يعمل للمصادر الثلاثة عبر `/go/{slug}?s=web&u=`). آخر قيمة غير-NULL لكل شخص، فلتر `is_proxy IS NOT TRUE AND is_datacenter IS NOT TRUE`. من لم ينقر رابطاً = «غير معروف» (بلا fallback لمدينة التسجيل، بلا تزييف). يُربط بـ [[data-trust-geo-device]].

**اللغة:** `bot_users.lang` (بوت+ميني) / `web_users.lang` (موقع)، قيم `ar`/`en`. النشط/الخامل في الداشبورد = `last_seen` (نشط < 20 يوم، خامل ≥ 20).

**حفظ اللغة (مبني 2026-06-05):** كان تبديل اللغة في الموقع (`lib/lang.tsx`) والميني-ويب (`miniapp.html`) يُحفظ في localStorage فقط ولا يصل القاعدة → `web_users.lang` كان عالقاً على `ar` للجميع. أُضيف `POST /track/set-lang` (api/routers/track.py): web→`web_users.lang`, telegram_miniapp/bot→`bot_users.lang`. الآن التبديل يُحفظ (آخر اختيار) لإرسال المنشورات بلغة المستخدم. البوت يعرض اللغة مرة واحدة فقط (onboarding)؛ الميني-ويب هو مكان تغييرها لاحقاً.

ملاحظة تواصل: المستخدم يكره الحشو والكلام الفاضي والـ meta-labels — اعرض الرقم والقرار مباشرة. لا تنبّه بحالات منتهية/بيانات ستُمسح. اشتغل: اسحب البيانات + سوِّ المطلوب فقط، بلا منطق مخترع.
