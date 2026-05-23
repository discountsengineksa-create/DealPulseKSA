"""
SEO Page Generator (Week 5-6) — خط أنابيب توليد صفحات هبوط تلقائية:

  1. trends.aggregate_internal_search()  — يجمّع سجلّ البحث (direct_search)
     في trend_signals (مصدر مجاني، بلا مفاتيح خارجية).
  2. matcher.match_and_enqueue()         — يطابق الكلمة بمتجر في master،
     يطبّق seo_keyword_blocklist، ويُنشئ seo_generation_jobs.
  3. generator.process_pending_jobs()    — يعالج الوظائف عبر الـ LLM
     (purpose='seo_copy' — نفس طبقة Gemini→OpenRouter + الحارس المالي)
     ويكتب seo_landing_pages كـ draft.
  4. indexer.submit_page()               — عند النشر: revalidate + IndexNow
     (يُتخطّى بهدوء إن لم تُضبط متغيرات البيئة).

المراحل 1-2 مجانية (بلا LLM) وتعمل بالـ scheduler. المرحلة 3 تستهلك
ميزانية LLM فمحكومة بـ SEO_AUTOGEN_ENABLED (افتراضي مُعطّل) + trigger يدوي.
"""
