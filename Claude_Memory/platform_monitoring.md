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

2. **الضوابط** `platform_settings` (جدول key/value، migration_032) + `api/utils/settings.py`. يقرأها `run_directive_cycle` في `api/workers/directive_generator.py`: `directive_enabled` (المفتاح الرئيسي — إيقافه يوقف الإيميلين)، `directive_recipient` (بريد بديل). **`directive_min_hours` أُلغي تطبيقه ٢٠٢٦-٠٩-٠٦** (الـcron صار يتحكّم بالإيقاع) — الحقل ما زال في UI الداشبورد لكنه بلا أثر.

3. **النشرة الدورية** `api/workers/directive_generator.py::run_directive_cycle(mode)` — **أُعيدت هندستها ٢٠٢٦-٠٩-٠٦** (كانت interval كل ٣ ساعات + جسم توجيهات فارغ غالباً + تسريب model/token/cost). الآن جدولان في `scheduler.py`:
   - **`directive_daily`** — cron ٧:٠٠ الرياض يومياً. `mode="daily"`: بيانات فقط، **بلا LLM**، ترسل دائماً (heartbeat). الموضوع فيه نقرات ٢٨ي + عدد المستخدمين.
   - **`directive_weekly`** — cron الاثنين ٧:٣٠ الرياض. `mode="weekly"`: كل ما في اليومي + جدول اتجاه البحث ٤ أسابيع + توجيهات LLM (`generate_directive`).
   - أُزيل footer الـ`النموذج/cache/tokens/تكلفة` من الإيميل — تلك تلمترية تبقى بلوحة الداشبورد.
   - الشارة: `warning` لو `_health_urgent` (توقّف/تهديد/قفزة)، وإلا `info`.

3ب. **تقرير صحة المنصة** `api/utils/platform_health.py::build_health_report(weekly=False)` — بيانات حقيقية لا LLM: إجمالي المستخدمين، أعلى ٣ متاجر نسخاً/نقراً (٧ أيام)، أداء الموقع، الأمان، قفزة حقيقية، المتاجر البرتقالية (١-٣ أيام)، فجوات البحث (**الآن ≥٢ بحثة + عربي فقط** — كان يُظهر ضجيج كلمة إنجليزية واحدة).
   **قسم البحث (GSC) أُضيف ٢٠٢٦-٠٩-٠٦:** يقرأ `seo_perf_snapshots` (صفّ = نافذة ٢٨ يوماً؛ الأحدث مقابل ما قبله بأسبوع) + `seo_gsc_pages` لأكثر الصفحات صعوداً/هبوطاً. `weekly=True` يضيف `gsc_trend` (٤ لقطات بفارق ~٧ أيام). المصدر يملؤه كرون `seo_snapshot_daily` (٤ص) من service account — **لا اعتماد جديد**.

4. **مراقبة أداء API** `api/utils/request_metrics.py` + middleware في `bot_app.py` (الإنتاج، مو main.py) → جدول `api_request_metrics` (migration_033). buffer في الذاكرة + flusher thread كل 5ث، احتفاظ 7 أيام. يعطي p95/متوسط الزمن + نسبة 5xx + أبطأ المسارات. قسم «أداء الموقع» في التقرير يستخدمه مع fallback تقريبي.

**قرار معماري:** رفضنا حشر latency في action_logs (يلوّثه + يفوّت معظم الطلبات) لصالح جدول مخصّص + middleware. المنصة لا تجمع uptime خارجي — اقتُرح UptimeRobot/Sentry لكن المستخدم اختار التتبّع الداخلي.

النموذج الافتراضي للتوجيهات: Groq llama-3.3-70b (Gemini غير مفعّل → fallback). مفصّل في [[project_overview]].

**لقطة الـLLM (`llm_service.build_input_snapshot`) وُسّعت ٢٠٢٦-٠٩-٠٦:** `window_hours` ٤٨→١٦٨، وأُضيف `store_activity_7d` (من `action_logs` مباشرة لأن المصفوفة المادّية ٤٨س فقط) + `search_28d` + `top_search_queries_28d` (عربي فقط) من جداول `seo_*`. السبب: بـ~٣٠ حدث/يوم كانت نافذة ٤٨س بلا إشارة فيرجع النموذج `directives: []`. `SYSTEM_PROMPT_AR` صار يطلب توجيهات محتوى/سيو لا كوبونات فقط. يتقاطع مع [[marketing_baseline_and_strategy]] و [[seo_indexation_status]].
