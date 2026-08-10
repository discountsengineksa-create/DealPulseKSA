# Content Quality / E-E-A-T / AI-Citation Audit — www.dealpulseksa.com

**Method:** Sampled 4 URLs via `claude-seo run render_page.py --mode auto --json` (raw fetch, `is_spa: false` confirmed on every page — server-rendered, no Playwright needed) plus a direct `curl` of `/sitemap.xml`. No Claude_Memory files were opened this session — all claims below are traced to a live fetch listed under "Sources," not to memory-file titles.

**Hard limitation, disclose up front:** the render tool's `extracted_text` field (trafilatura, boilerplate-stripped) truncates at ~500 characters for the blog article and appears truncated for the calendar page (both strings end in a literal `...` or ambiguous `....`). The homepage and store-page `extracted_text` do **not** end in a truncation marker — those two are confirmed complete. Word counts below are marked **measured (full)**, **measured (truncated, partial only)**, or **inferred**.

## Sources (raw data saved this session)

| # | URL | Captured to |
|---|---|---|
| 1 | `https://www.dealpulseksa.com/` | `seo/audits/www.dealpulseksa.com-audit/homepage-render.json` (pre-existing) |
| 2 | `https://www.dealpulseksa.com/calendar` | stdout only, not saved to disk |
| 3 | `https://www.dealpulseksa.com/blog/perfume-brands-celebrity-saudi-arabia` | scratchpad `blog.json` |
| 4 | `https://www.dealpulseksa.com/store/سويتر` (`/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1`) | scratchpad `store.json` |
| — | `https://www.dealpulseksa.com/sitemap.xml` | curl, stdout only — **1748 `<loc>` entries counted** (`grep -c "<loc>"`), confirms blog URLs (`/blog/perfume-brands-*`) and `/store/[slug]` URLs exist as separate templates |

---

## Overall Content Quality Score: **~43/100** (low confidence, n=4)

This is a per-sampled-page average, not a site-wide measurement. Do not treat as a site verdict — treat as a directional signal that says "sample more before deciding a remediation budget."

| Page type | URL | Score | Confidence |
|---|---|---|---|
| Homepage | `/` | 38/100 | Medium (full extracted_text measured) |
| Store page | `/store/سويتر` | 24/100 | Medium (full extracted_text measured) |
| Blog article | `/blog/perfume-brands-celebrity-saudi-arabia` | 53/100 | **Low — n=1, only first 83 words visible** |
| Calendar hub | `/calendar` | 57/100 | Low-medium (preview only, not full text) |

---

## E-E-A-T Breakdown

Weights per this skill's model: Experience 20% / Expertise 25% / Authoritativeness 25% / Trustworthiness 30%.

### Homepage (`/`) — measured, extracted_text complete: **51 words / 293 characters**
This is the FULL boilerplate-stripped prose trafilatura found — not a snippet. It consists of a hero line ("مُحدَّث الآن مباشرةً"), a tagline ("لا تدفع السعر كامل ما دام فيه خصم بانتظارك"), and 4-5 short CTA phrases ("تصفّح حسب التصنيف", "أعثر على ما يناسبك بسرعة", "افتح البوت"). The actual store/deal grid that almost certainly renders below the hero was either not present in this raw HTML fetch's readable-content classification or was stripped by trafilatura as repeated-card boilerplate — **this needs a DOM inspection to confirm which**, flagged as unresolved, not claimed either way.
- Structured data: **1 JSON-LD block**, types `ContactPoint, Country, EntryPoint, ImageObject, OnlineBusiness, Organization, PostalAddress, SearchAction, WebSite` (measured from `structured_data.blocks[0].types`). Real business-identity schema (address, contact point) — a genuine Trustworthiness signal, though field *values* weren't expanded/verified this session.
- Experience 20 / Expertise 30 / Authoritativeness 40 / Trustworthiness 55 → weighted **38/100**.
- Gap: against the skill's Homepage floor (500 words), the extractable prose is **51 words — 10% of the floor**. Whether this is a real thin-content problem or an artifact of how trafilatura treats card-grid layouts is the single most important thing to verify next (see recommendations).

### Store page (`/store/سويتر`) — measured, extracted_text complete: **63 words / 327 characters**
Confirmed complete (no truncation marker). Full text is two FAQ-style Q&As:
- "كيف أستخدم كوبون سويتر؟" → 3-step redemption instructions naming the code `TZ3F`.
- "هل كوبون سويتر مجاني؟" → "نعم، استخدام جميع كوبونات نبض الصفقات مجاني تماماً. نحن نحصل على عمولة من المتجر فقط عند إتمامك للشراء — دون أي تكلفة إضافية عليك." (commission-disclosure sentence — a real Trustworthiness positive).
- Structured data: **only 2 blocks** — sitewide Organization/WebSite (same block as homepage) + `BreadcrumbList` (409 bytes). **No Product, Offer, or FAQPage schema**, despite the page literally being an FAQ pattern and literally containing a discount code + merchant. The two facts an AI answer engine would most want to cite — the code `TZ3F` and "free to use" claim — exist only as unstructured prose, not as machine-extractable entities.
- `Cache-Control` header on this page: `private, no-cache, no-store, max-age=0, must-revalidate` (measured) — versus the homepage's `public, max-age=0, must-revalidate`. Store pages are marked **private/no-store**, unusual for public commercial content and worth a flag to whoever owns technical caching (out of this skill's scope, noted for handoff).
- Experience 10 / Expertise 15 / Authoritativeness 20 / Trustworthiness 45 → weighted **24/100**.
- Against this skill's Product-page floor (300-400+ words for "complex products"; a coupon page is arguably simpler, but even the lowest floor in the table is 5x this page's word count), **63 words is genuinely thin content**, not a truncation artifact.
- QRG "repetitive structure across pages" flag: the exact two-question template ("كيف أستخدم كوبون [X]؟ / هل كوبون [X] مجاني؟") is very likely reused verbatim across the store template for every merchant (sitemap shows hundreds of `/store/[slug]` URLs). **Not counted this session** — this is inferred from one sample plus the sitemap's URL pattern, flag for a follow-up crawl of 10-15 store pages to confirm the template is literally identical besides the store name/code.

### Blog article (`/blog/perfume-brands-celebrity-saudi-arabia`) — **measured, TRUNCATED: 83 words / 503 characters visible, true total unmeasured**
The render tool cut this off mid-sentence with a literal `...`. What's visible: title "عطور الترخيص: المشاهير وماركات السيارات والشخصيات", a specific framing sentence, and an explicit affiliate disclosure: *"إفصاح: هذه الصفحة تحتوي روابط لمتاجر شريكة وكود خصم يخصّ زوّار نبض الصفقات، ونحصل على عمولة... القوائم مبنية على كتالوج المتجر المنشور وقت الكتابة وقد تتغيّر."* — an explicit "content may go stale" caveat, which is a genuine first-hand-editorial-honesty signal, not generic AI filler.
- Structured data: **4 JSON-LD blocks** — (1) sitewide Organization/WebSite, (2) `BlogPosting + Organization + WebPage` (776 bytes — article-level with publisher wrapper), (3) `BreadcrumbList` (621 bytes), (4) `ItemList + ListItem` (1426 bytes — a structured list of the perfume brands covered, strong AI-citation signal *if* the list items carry real brand names, not verified this session).
- `publication_date`: **2026-08-06** (htmldate-detected) — 4 days before this audit, a positive freshness signal (measured, but htmldate accuracy on this specific page not independently cross-checked).
- Experience 35 / Expertise 55 / Authoritativeness 45 / Trustworthiness 70 → weighted **53/100**. Trustworthiness scores highest here specifically because of the explicit affiliate disclosure — rare, valuable, and directly what the Sept-2025 QRG rewards.
- **This is a single sample out of 1564 blog articles and only the first ~83 words of that one.** No conclusion about the other 1563 articles' prose quality can be drawn from this file. See hypothesis section below.

### Calendar hub (`/calendar`) — preview only, **not fully measured**
Visible text: *"موعد التخفيضات في السعودية 2026 — هذا دليل مرجعي لمواعيد أقوى المواسم — الجمعة البيضاء، اليوم الوطني، يوم التأسيس، رمضان والعيدان، تخفيضات نهاية الموسم، العودة للمدارس و11.11..."* plus a tactical "كيف تستفيد" section and — most notably — an explicit accuracy caveat: *"⚠️ مواسم رمضان والعيدين تتبع التقويم الهجري وتُحدَّد برؤية الهلال، لذا تواريخها هنا تقديرية لسنة 2026."* (dates are estimates because Ramadan/Eid follow lunar sighting). This is a specific, honest, non-generic disclosure — directly contradicts the QRG's "generic phrasing, no original insight" AI-slop marker.
- Structured data: **5 JSON-LD blocks** (measured: `structured_data.block_count: 5`) — the richest of the four sampled pages. Types not expanded this session (truncated stdout), flagged as unverified detail.
- Experience 50 / Expertise 60 / Authoritativeness 50 / Trustworthiness 65 → weighted **57/100**, but confidence is low because full word count wasn't captured.

---

## AI Citation Readiness Score: **~45/100**

Gated primarily by two things, both directly observed:
1. **The highest-commercial-intent page type (store pages) has the weakest structured data.** Homepage and store pages both cap out at Organization/WebSite + Breadcrumb. The actual queryable facts — a specific code, a specific store, "is it free" — sit in 63 words of plain prose with no `Offer`/`FAQPage` wrapper. An AI answer engine extracting facts the way trafilatura does would find almost nothing to cite on the one page type designed to answer "does dealpulseksa have a working X code."
2. **The blog template does markup correctly** (`BlogPosting` + `ItemList` + `BreadcrumbList`) — this is a real strength and should be the pattern extended to store pages, not the other way around.

| Page type | Schema blocks (measured) | Verdict |
|---|---|---|
| Homepage | 1 (Organization/WebSite) | Baseline only |
| Store | 2 (+ BreadcrumbList) | **Weakest — missing Offer/FAQPage** |
| Blog | 4 (+ BlogPosting, ItemList) | Good pattern |
| Calendar | 5 (count only, types unverified) | Richest observed |

---

## Hypothesis test: is the 710/764 zero-click blog problem content quality or keyword selection?

Given context: 710 of 764 blog pages earn zero clicks; many rank positions 1-4 with 1-2 impressions.

**Evidence gathered this session is consistent with the keyword-selection-failure hypothesis, but is far too thin to confirm it — say so plainly rather than overclaim:**
- The one blog article sampled (`perfume-brands-celebrity-saudi-arabia`) shows a specific, non-generic editorial voice, an explicit affiliate disclosure, a "content may go stale" caveat, and 4 correctly-nested schema blocks including an `ItemList`. None of the QRG's AI-slop markers (generic phrasing, no original insight, no first-hand signal, repetitive structure) are visible in what I could read.
- **But this is n=1 of 1564 articles, and even that one sample was cut off by the tool at 83 words** — I did not see the article's body, only its opening. I cannot rule out that quality degrades mid-article or that other articles in the corpus are templated/thin the way store pages measurably are.
- Ranking positions 1-4 with only 1-2 impressions is itself evidence pointing away from a content-quality explanation and toward a demand/keyword-selection explanation: Google does not typically rank thin or low-quality content at position 1-4 for a query with real search volume — it's far more consistent with targeting queries that have near-zero actual search volume (the article ranks well because there's negligible competition, not despite thin content).
- **Independent of that hypothesis**, store pages have a *measured*, not inferred, thin-content problem (63 words, missing Offer/FAQPage schema) that would suppress both rankings and AI-citation eligibility regardless of keyword targeting. This is a different page type from the 710/764 blog figure and should not be conflated with it — but it's the more actionable, better-evidenced finding from this session.

**Verdict: evidence leans toward keyword-selection failure for the blog cohort (not proven, n=1) — and toward a genuine, measured content-thinness failure for the store-page cohort (proven for the one page sampled, template pattern inferred for the rest).**

---

## Recommendations, ranked by evidence strength

1. **(Measured, high-confidence) Add `Offer` + `FAQPage` JSON-LD to the `/store/[slug]` template.** The code, discount type, and merchant are already in the prose (`TZ3F`, "سويتر") — this is a schema-authoring task, not a content-authoring task. Directly improves AI-citation readiness for the page type with the most transactional intent.
2. **(Inferred, needs a 10-15 page follow-up crawl) Confirm whether the two-question FAQ template is verbatim-identical across all `/store/[slug]` pages.** If so, this is exactly the QRG's "repetitive structure across pages" red flag at scale (hundreds of URLs per the sitemap) and should get either genuine per-store differentiation (return policy nuances, shipping-to-KSA specifics, category context) or `noindex` on the lowest-value tail, per the "White-Hat only, no scaled low-value pages" constraint already in this repo's CLAUDE.md.
3. **(Unresolved, needs DOM inspection not just trafilatura) Verify whether the homepage's store/deal grid is genuinely thin or just stripped by the extraction tool.** Re-run `render_page.py --mode always` (force Playwright) or open `raw_content`/`content` (not `extracted_text`) for the homepage and manually check whether the below-the-fold deal cards contain real per-store data. Don't remediate word count on the homepage until this is confirmed either way — fabricating a "thin homepage" fix against an extraction-tool artifact would waste effort.
4. **(Low-confidence, n=1) Do not assume the 1564-article blog corpus is content-quality-clean based on this one sample.** Before accepting the keyword-selection-failure hypothesis as the full explanation for 710/764 zero-click pages, pull full (untruncated) text for a real sample (10-20 articles stratified across clusters) and check mid-article and closing sections, not just the opening 83 words.
5. **(Measured) The store-page `Cache-Control: private, no-store` header is anomalous for public content** — hand off to whoever owns technical/crawlability findings; it may affect re-crawl frequency independent of content quality.

---

## Structured summary (for `audit-data.json` ingestion)

```json
{
  "category": "content_quality",
  "url_scope": "https://www.dealpulseksa.com",
  "overall_score": 43,
  "confidence": "low — n=4 URLs sampled",
  "pages": [
    {"url": "https://www.dealpulseksa.com/", "type": "homepage", "word_count": 51, "word_count_status": "measured_full", "schema_blocks": 1, "score": 38},
    {"url": "https://www.dealpulseksa.com/store/سويتر", "type": "store", "word_count": 63, "word_count_status": "measured_full", "schema_blocks": 2, "score": 24, "flags": ["thin_content", "missing_offer_schema", "missing_faqpage_schema", "cache_control_private_anomaly"]},
    {"url": "https://www.dealpulseksa.com/blog/perfume-brands-celebrity-saudi-arabia", "type": "blog", "word_count": 83, "word_count_status": "measured_truncated_partial_only", "schema_blocks": 4, "score": 53, "flags": ["sample_size_n1", "positive_disclosure_signal"]},
    {"url": "https://www.dealpulseksa.com/calendar", "type": "hub", "word_count": null, "word_count_status": "not_measured_preview_only", "schema_blocks": 5, "score": 57}
  ],
  "ai_citation_readiness_score": 45,
  "hypothesis_test": {
    "question": "710/764 zero-click blog pages: content quality vs keyword selection",
    "verdict": "leans keyword-selection for blog cohort (n=1, not proven); store-page thin-content is separately measured and proven for the sampled page"
  }
}
```
