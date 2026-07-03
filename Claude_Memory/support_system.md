---
name: support-system
description: نظام الدعم الفني — معماريته المعتمدة وما هو مبني (بوت + داشبورد + API)
metadata: 
  node_type: memory
  type: project
  originSessionId: 61c1bcf7-09f5-4fff-bf12-77d11745e663
---

نظام الدعم في «نبض الصفقات» = **وسيط عبر Telegram Bot API فقط**. المالك رفض صراحةً: قروبات تلجرام، الأرقام الشخصية، و(مؤقتاً) وكيل AI.

**المعمارية المعتمدة (بلا webhook):** بوت الـ polling لا يمكنه تشغيل webhook + polling على نفس التوكن، فالاستقبال يتم داخل البوت الحالي مباشرةً (لا webhook منفصل).

**المبني والمنشور على الإنتاج:**
- البوت: زر «🆘 الدعم» (state='support' في handle_nav) → `_process_support` يحفظ تذكرة `source='bot'` مع `telegram_id`+`username`.
- الميني (`miniapp.html`): زر 🆘 بالهيدر + bottom-sheet → `POST /api/v1/track/support`.
- API (`api/routers/track.py` + `schemas/track.py`): endpoint `/track/support` يكتب التذكرة (يسحب snapshot هوية الموقع من web_users).
- الداشبورد «مركز الدعم»: يعرض الهوية (يوزر/إيميل/جوال/المصدر/telegram_id) ويرد فعلياً عبر `_tg_send`/`send_reply_to_user(chat_id, reply)` بـ `BOT_TOKEN` (Telegram sendMessage)، ويحفظ `reply_text/replied_at/delivered` + أرشيف.
- `migration_039_support_tickets_upgrade.sql` مطبّق على الإنتاج: أضاف `source, web_user_id, contact_name/email/phone, reply_text, replied_at, delivered` + index.
- أمر `/chatid` أُضيف للبوت (كان لفكرة القروب المرفوضة — غير ضار، مجرد يطبع chat id).

**باقٍ (لم يُبنَ):** زر الدعم في موقع الويب (`dealpulseksa-web` — repo منفصل، يُنشر مستقلاً). فكرة المالك: دعم الموقع يمر عبر تلجرام بـ deep-link لالتقاط يوزر تلجرام وربطه (يصير «مكتمل»). انظر [[unified_favorites]].

**PDPL:** تقليل البيانات، احتفاظ ≤6 أشهر ثم anonymize للمُغلقة، secret_token لو استُخدم webhook لاحقاً، حق الحذف عبر anonymize.

مرتبط بـ [[store-analytics-bi]] (نفس نمط استدعاء LLM لو رجعنا لوكيل AI لاحقاً).
