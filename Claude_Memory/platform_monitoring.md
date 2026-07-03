---
name: platform-monitoring
description: منظومة «متابعة المنصة» — صفحة داشبورد + تقرير صحة بالإيميل + مراقبة أداء API
metadata: 
  node_type: memory
  type: project
  originSessionId: f7f4b8a9-28b1-4dc2-85df-56107e47a4f4
---

منظومة مراقبة بناها المستخدم تدريجياً (يونيو 2026) لمتابعة المنصة خوفاً من التعليق/الانهيار. أربعة أجزاء مترابطة:

1. **صفحة الداشبورد** «🛰️ متابعة المنصة» (أدوات متقدمة) في `dashboard.py` — تبويبات: التوجيهات، استهلاك الذكاء، التنبيهات والكاش، الضوابط. تقرأ ai_directives/llm_call_log/ai_alerts/llm_semantic_cache.

2. **الضوابط** `platform_settings` (جدول key/value، migration_032) + `api/utils/settings.py`. يقرأها `run_directive_cycle` في `api/workers/directive_generator.py`: `directive_enabled` (تشغيل/إيقاف)، `directive_min_hours` (تقييد فاصل الإيميلات)، `directive_recipient` (بريد بديل).

3. **تقرير صحة المنصة** `api/utils/platform_health.py` — يُلحَق بكل إيميل توجيهات (بيانات حقيقية لا LLM): إجمالي المستخدمين، أعلى 3 متاجر نسخاً/نقراً (كل القنوات، آخر 7 أيام)، أداء الموقع، الأمان، قفزة حقيقية، المتاجر البرتقالية (1-3 أيام)، فجوات البحث.

4. **مراقبة أداء API** `api/utils/request_metrics.py` + middleware في `bot_app.py` (الإنتاج، مو main.py) → جدول `api_request_metrics` (migration_033). buffer في الذاكرة + flusher thread كل 5ث، احتفاظ 7 أيام. يعطي p95/متوسط الزمن + نسبة 5xx + أبطأ المسارات. قسم «أداء الموقع» في التقرير يستخدمه مع fallback تقريبي.

**قرار معماري:** رفضنا حشر latency في action_logs (يلوّثه + يفوّت معظم الطلبات) لصالح جدول مخصّص + middleware. المنصة لا تجمع uptime خارجي — اقتُرح UptimeRobot/Sentry لكن المستخدم اختار التتبّع الداخلي.

النموذج الافتراضي للتوجيهات: Groq llama-3.3-70b (Gemini غير مفعّل → fallback). مفصّل في [[project_overview]].
