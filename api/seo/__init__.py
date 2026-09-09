"""
SEO landing-page tools — **manual only** (auto-generation removed 2026-09-09
at owner's request; the 3am auto cycle was already removed 2026-09-05).

Flow now:
  1. /admin/seo-seed-custom — owner types a topic → queues seo_generation_jobs
     for the top stores (explicit human trigger).
  2. generator.process_pending_jobs() — processes queued jobs via the LLM
     (purpose='seo_copy' — Gemini→OpenRouter + financial guardian), writes
     seo_landing_pages as draft. Triggered by /admin/seo-run or the
     per-keyword button in the opportunities page.
  3. Owner reviews drafts and publishes them from the dashboard.
  4. indexer.submit_page() — on publish: revalidate + IndexNow.

matcher._is_blocked() is still used by the generator as a White-Hat gate.
There is no keyword discovery, no match_and_enqueue, no long-tail seeder,
and no scheduled generation.
"""
