# GEO / AI Search Readiness — www.dealpulseksa.com

Audited 2026-08-10. Live checks performed this pass: `robots.txt` (full fetch),
`llms.txt` (full 591,747-byte fetch + structural analysis), homepage render
JSON (`homepage-render.json` in this audit folder). Brand-mention presence on
Wikipedia/Reddit/YouTube/LinkedIn was **not independently re-verified this
pass** — see §4, which is explicitly marked as inferred from prior project
memory, not fresh measurement.

## GEO Readiness Score: 44/100

Analytical score per the 5-dimension rubric, weighted average of the
per-dimension scores below (0.25×40 + 0.20×55 + 0.15×35 + 0.20×25 + 0.20×65 =
44.25). This is a judgment score applying the rubric to the evidence gathered
— not a platform-reported citation-rate metric (no DataForSEO tool was
available/invoked this session).

| Dimension | Weight | Score /100 | Basis |
|---|---|---|---|
| Citability | 25% | 40 | Good FAQ *format*, but answers are 9–16 words (see §3) against a 134–167 optimal target, and the one passage that does hit good length is buried at 97% depth in the file |
| Structural Readability | 20% | 55 | Server-rendered HTML (see §5), Q&A headings inside the AI block, but store/blog sections are flat one-line bullets with no per-entry freshness dates |
| Multi-Modal Content | 15% | 35 | Homepage schema has `ImageObject` only; no `VideoObject`/on-page video evidence found — under-verified, flagged not measured |
| Authority & Brand Signals | 20% | 25 | Solid on-page entity markup (§5), but per project memory: ~5 bot users + 10 web accounts + zero broadcast reach, and the owned-channel strategy explicitly excluded Reddit/Quora — the framework's two strongest correlation signals (YouTube 0.737, Reddit "high") are structurally unaddressed |
| Technical Accessibility | 20% | 65 | All 15 AI-specific crawlers explicitly allowed (§1), SSR confirmed, but the 578 KB llms.txt and percent-encoded Arabic URLs create real ingestion-size risk (§2) |

---

## 1. AI Crawler Access — `robots.txt` (fetched live, 200 OK)

Every block below is `Allow: /` with the identical narrow disallow list
(`/account`, `/login`, `/register`, `/forgot-password`, `/api/`). **16
`User-Agent` blocks total** (the wildcard `*` plus 15 named bots) — counted
directly from the fetched file, no crawler is blocked:

| Crawler | Status | Notes |
|---|---|---|
| GPTBot | Allowed | ChatGPT training/answer crawler |
| OAI-SearchBot | Allowed | Powers ChatGPT search citations |
| ChatGPT-User | Allowed | Live browsing-tool fetches |
| ClaudeBot | Allowed | |
| anthropic-ai | Allowed | |
| Claude-Web | Allowed | |
| PerplexityBot | Allowed | |
| Perplexity-User | Allowed | Live browsing-tool fetches |
| Google-Extended | Allowed | Governs Gemini/AI Overviews training use |
| CCBot | Allowed | Common Crawl — training only, the skill's own table lists this as "optional block," site has chosen to allow it |
| cohere-ai | Allowed | Same — training-only, allowed rather than blocked |
| Applebot-Extended | Allowed | |
| Bytespider | Allowed | ByteDance/TikTok crawler |
| DuckAssistBot | Allowed | |
| Meta-ExternalAgent | Allowed | |

`Sitemap: https://www.dealpulseksa.com/sitemap.xml` and `Host:` directives
present. **No crawler is restricted.** This is the most generous posture
possible — every framework-recommended "allow" bot is allowed, and both
framework-recommended "optional block" bots (CCBot, cohere-ai) are allowed
too. Not a defect, but worth the owner knowing it's a deliberate choice, not
an oversight: training-data crawlers get the same unrestricted access as
answer-engine crawlers. `/calendar` carries no page-specific disallow — it is
covered by the same blanket `Allow: /`.

## 2. llms.txt — present, 200 OK, structurally risky at scale

Confirmed size: **591,747 bytes / 1,803 lines** (measured with `wc -c`/`wc -l`
on the live fetch — the task brief's 591,747 B / 1,804-line figures match
within one line of rounding). Section order, measured with `grep -n "^## "`:

```
9    ## أقسام رئيسية        (main sections)
19   ## أدلّة أكواد الخصم    (code guides)
82   ## المتاجر             (stores — codes published inline)
136  ## التصنيفات            (categories)
176  ## المدوّنة             (blog — runs 1,563 lines)
1739 ## للأنظمة الذكية       (for AI systems — summary + FAQ)
1800 ## معلومات إضافية       (contact/sitemap)
```

**(a) Size/truncation problem.** Lines 82–1738 (stores + categories + blog
link list) measure **574,092 bytes — 97.0% of the file** (measured directly:
`sed -n '82,1738p' llms.txt | wc -c`). That is a flat inventory of link +
one-line-description entries, not full article text (average 328
bytes/line across the whole file). Most RAG-style page fetchers used by
answer engines (ChatGPT browsing tool, Perplexity's fetcher) apply a
per-page ingestion cap — commonly well under 578 KB — before summarizing a
source. **The section engineered specifically for AI citation — the
executive summary + 13-question FAQ — sits at byte-depth ~97%, in the last
3.5% of the file.** If any client truncates (a near-certainty at this size),
it reads 1,563 blog links and 52 bare-code store lines and never reaches the
one block written for it. This is the single highest-leverage structural fix
available (see recommendation #2).

Separately: percent-encoded Arabic URLs are byte- and token-expensive. Measured
directly on one entry: the store slug `مترو البرازيل` (13 Arabic characters)
encodes to a **112-byte** URL (`sed -n '83p' llms.txt | grep -oP
'https://[^)]+\)' | wc -c`). With roughly 1,615 links in the file (52 stores +
~1,563 blog posts, per the section boundaries above), the encoded-URL tax
alone accounts for a meaningful share of both the 578 KB and of the token
count an LLM client would burn just parsing paths, before it reads a single
word of description.

The original llms.txt convention (Answer.AI/Jeremy Howard) is a **concise,
curated navigational index**, with exhaustive detail deferred to a linked
`llms-full.txt`. At 578 KB this file is the opposite of that — it is the
full catalogue inline, which both risks truncation and works against the
convention's intent.

**(b) Attribution leak — confirmed, not hypothetical.** The المتاجر section
publishes a bare discount code next to every store, with zero distinction
between code-attributed and click-attributed merchants. Sample lines pulled
directly from the live file:

```
- [مترو البرازيل](.../store/...): خصم 10% — كود الخصم: CMM236
- [سويتر](.../store/...): خصم 15% — كود الخصم: TZ3F
- [منصة زد](.../store/...): خصم 20% — كود الخصم: 52024731016
```

**Zid is the concrete leak.** Per this repo's own memory
(`Claude_Memory/zid_affiliate_channel.md`): Zid's affiliate program pays
**"إسناد بالرابط فقط"** — attribution by tracking-link click only, no
code-based attribution. Yet line 133 of llms.txt publishes a bare Zid code
(`52024731016`) with no CTA to the tracking link. Any AI system that reads
llms.txt and hands a user this code produces a completed purchase with
**zero commission back to the site** — the exact failure mode the task
brief describes, now shown to be live on at least one confirmed merchant,
not theoretical. The same risk applies to every other click-attributed
partner in the file; without a per-store attribution flag there is no way to
audit the rest from the file alone. Recommend: add an `attribution_model`
column (`code` | `click`) to `master`, and have the llms.txt/store-page
generator suppress bare codes for `click` merchants in favor of a tracking-
link CTA line. This is a data-layer fix, not a content-editing one — same
principle already documented in `feedback_prefer_codes_over_tracking_links.md`,
just not yet enforced in the AI-facing export.

**(c) No RSL 1.0 licensing.** `grep -i "rsl\|licens"` across the full file
returned zero matches. The file does carry one informal citation-permission
line inside the AI block ("يُسمح بالاقتباس مع الإشارة للمصدر
dealpulseksa.com") but no machine-readable RSL 1.0 block. Low urgency — RSL
is an emerging, not yet widely-consumed convention — but if the owner wants
explicit AI-training terms, this is the gap.

## 3. Citability — the AI-facing block itself, word-counted

The `## للأنظمة الذكية` block (lines 1739–1799) is well-formed as *format*:
one authoritative summary blockquote + "ما يميّز" bullets + 13 Q&A pairs in
`**س:**/ج:` style, closing with an explicit citation-permission line. But
measured against the skill's 134–167-word optimal-passage guidance, every
individual answer is far too short to be quoted with confidence rather than
paraphrased. Word counts (Python `str.split()` on the exact retrieved text):

| Passage | Words | vs. 134–167 target |
|---|---|---|
| Executive-summary blockquote (the one passage with real information density — 52 stores, 1,561 articles, 61 code pages, category list) | 86 | Under target, closest of all |
| "هل نبض الصفقات مجاني؟" | 9 | Far under |
| "هل يجب أن أُنشئ حساباً…؟" | 16 | Far under |
| "هل الكوبونات تعمل فعلاً؟" | 15 | Far under |

Self-containment is good (each answer stands alone without needing the rest
of the page), and the summary line explicitly disambiguates the brand from
"البورصة العقارية" (a real, correct name-collision defense). But the FAQ
answers are single-sentence and will more likely get paraphrased into a
generic AI answer than quoted verbatim as a citable source, because they
lack the supporting statistic/date detail that gives a model confidence to
attribute a direct quote.

## 4. Brand-mention / authority signals — not independently re-verified

No live search of Wikipedia, Reddit, YouTube, or LinkedIn was run this pass.
What follows is drawn from existing project memory, **explicitly flagged as
such, not as fresh measurement**:

- `Claude_Memory/owned_audience_reality.md`: ~5 Telegram bot users, ~10 web
  accounts, zero broadcast reach as of last count.
- `Claude_Memory/seo_owned_channels_pivot.md`: Reddit and Quora were
  deliberately rejected as promotion channels in favor of X/Telegram/Instagram.
- `Claude_Memory/domain_authority_plan.md`: backlink/domain-authority
  building is still an open program, not a completed one.
- `Claude_Memory/seo_audit_tools_trust.md`: Semrush data for this domain is
  frozen/stale — external DR/backlink numbers should not be quoted as current
  without a fresh pull.

Directionally, this means the framework's two strongest AI-citation
correlation signals — YouTube mentions (0.737, strongest) and Reddit presence
(high) — are both currently near-zero by the site's own prior documentation,
and one of them (Reddit) is the result of a deliberate strategic decision,
not an oversight. That decision may still be correct for other reasons (spam
risk, moderation cost), but it caps GEO ceiling on platforms — Perplexity in
particular — that weight those signals heavily. This is a tradeoff for the
owner to weigh, not something to silently reverse. On-page entity signal is
solid: homepage schema.org includes `Organization`, `WebSite`, `PostalAddress`,
`ContactPoint`, `SearchAction`, `OnlineBusiness`, `ImageObject` (measured
directly from `structured_data.blocks[0].types` in `homepage-render.json`,
2,001 bytes, valid, not truncated).

## 5. Technical Accessibility

From `homepage-render.json` (already captured for this audit, re-read this
pass, not re-fetched):

- `is_spa: false`, `mode_used: "raw"` — the render pipeline did not need to
  invoke Playwright, meaning content is present in the raw HTML response.
- Response headers confirm Next.js static/ISR prerendering:
  `X-Nextjs-Prerender: 1`, `X-Vercel-Cache: HIT`, `Content-Encoding: br`.
- `publication_date: "2026-08-10"` extracted via htmldate — present, though
  this reflects the render/revalidation timestamp for a dynamic homepage, not
  a per-article publish date; per-article dates should be checked at the
  blog-post level in a separate pass, not claimed here.

This dimension scores well specifically because SSR + full crawler allowlist
remove the two most common AI-crawler blockers (JS-only rendering, blanket
`Disallow`). The 65/100 is held down only by the llms.txt size/encoding
issues in §2, which are a content-delivery problem, not a rendering one.

## 6. Platform-Specific Assessment (qualitative — no live citation testing performed)

DataForSEO MCP tools were not available/invoked this session, so these are
directional assessments from crawler-access + content-structure evidence
above, not measured citation rates. Do not quote these as percentages.

| Platform | Assessment | Why |
|---|---|---|
| Google AI Overviews | Low–Medium | Google-Extended is allowed, on-page schema is solid, **but AI Overviews does not consume llms.txt at all** — it rides on the organic index and E-E-A-T signals, and prior audits in this repo (`seo_page_portfolio_verdict.md`) already show most indexed pages at zero clicks, which caps AIO surface area regardless of any GEO fix made here |
| ChatGPT (search/browsing) | Medium, undermined by structure | GPTBot/OAI-SearchBot/ChatGPT-User all allowed and llms.txt exists, but §2's burial problem means a live fetch is likely to never reach the curated AI block |
| Perplexity | Low–Medium | PerplexityBot/Perplexity-User allowed, but Perplexity's citation behavior leans on Reddit/YouTube signal per this framework's own correlation table, both of which are structurally weak here per §4 |
| Bing Copilot | Not independently tested this pass | Covered only by the wildcard `Allow: /` (no Bing-specific AI directive checked); relies on Bing's own index quality, out of scope for this fetch-based audit |

---

## Top 5 Highest-Impact Changes

| # | Change | Impact | Effort |
|---|---|---|---|
| 1 | **Stop the confirmed attribution leak.** Add a `master.attribution_model` flag (`code`/`click`); for click-attributed merchants (Zid confirmed, line 133 of llms.txt — `52024731016` — likely others unaudited), suppress the bare code in llms.txt and on the store page, replace with a tracking-link CTA | High — direct revenue leak, already proven live on ≥1 merchant | Low — one column + one generator-side filter |
| 2 | **Move the `## للأنظمة الذكية` block to the top of llms.txt**, right after the intro paragraph, before the store/category/blog inventory | High — the only content engineered for AI citation currently sits at 97% byte-depth of a 578 KB file, past most fetchers' ingestion caps | Low — reorder existing sections, no new content |
| 3 | **Split llms.txt into a short curated index (target well under 100 KB) + a linked `llms-full.txt`** carrying the 1,563-line blog inventory and full store list | Medium-High — restores the file to the llms.txt convention's intent and removes the truncation risk at the source instead of just reordering around it | Medium — build one additional export, link it from the trimmed llms.txt |
| 4 | **Lengthen the 13 FAQ answers toward 134–167 words** by adding one supporting sentence with a concrete stat/date to each (measured current lengths: 9, 15, 16 words vs. the 86-word summary blockquote, which is itself still under target) | Medium — short answers get paraphrased, not quoted; longer self-contained answers are what the citability research this skill is built on says gets quoted verbatim | Low — copy edit, no engineering |
| 5 | **Address the YouTube/Reddit signal gap** (0.737 and "high" correlation respectively per this framework, both near-zero per `owned_audience_reality.md`) — at minimum, on-page video content with proper `VideoObject` schema; Reddit is a deliberate strategic exclusion the owner should re-confirm, not silently reverse | Medium — highest-correlation signal in the whole framework, but requires new content production, not a config change | High — new content channel, not a technical fix |

---

## Structured summary (for `audit-data.json` — AI Search Readiness category)

```json
{
  "category": "ai_search_readiness",
  "url": "https://www.dealpulseksa.com",
  "audited_date": "2026-08-10",
  "geo_score": 44,
  "dimension_scores": {
    "citability": 40,
    "structural_readability": 55,
    "multi_modal_content": 35,
    "authority_brand_signals": 25,
    "technical_accessibility": 65
  },
  "robots_txt": {
    "status": "fetched_200",
    "ai_crawlers_allowed": ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "anthropic-ai", "Claude-Web", "PerplexityBot", "Perplexity-User", "Google-Extended", "CCBot", "cohere-ai", "Applebot-Extended", "Bytespider", "DuckAssistBot", "Meta-ExternalAgent"],
    "ai_crawlers_blocked": [],
    "disallow_paths": ["/account", "/login", "/register", "/forgot-password", "/api/"]
  },
  "llms_txt": {
    "status": "present_200",
    "size_bytes": 591747,
    "lines": 1803,
    "rsl_licensing": false,
    "ai_block_present": true,
    "ai_block_line_start": 1739,
    "ai_block_byte_depth_pct": 97.0,
    "attribution_leak_confirmed": true,
    "attribution_leak_example": "Zid store (line 133) — bare code 52024731016 published; Zid affiliate program is click-attribution only per zid_affiliate_channel.md"
  },
  "citability": {
    "faq_answer_word_counts_sample": [9, 15, 16],
    "summary_blockquote_word_count": 86,
    "optimal_range": [134, 167],
    "meets_optimal_length": false
  },
  "technical_accessibility": {
    "is_spa": false,
    "ssr_confirmed": true,
    "render_mode": "raw",
    "structured_data_types": ["ContactPoint", "Country", "EntryPoint", "ImageObject", "OnlineBusiness", "Organization", "PostalAddress", "SearchAction", "WebSite"]
  },
  "brand_signals": {
    "independently_verified_this_pass": false,
    "source": "project memory (owned_audience_reality.md, seo_owned_channels_pivot.md)",
    "youtube_presence": "not confirmed / likely minimal",
    "reddit_presence": "deliberately excluded by strategy",
    "wikipedia_entity": "not confirmed"
  },
  "platform_notes": {
    "google_ai_overviews": "does not consume llms.txt; relies on organic index + schema",
    "chatgpt": "llms.txt present but truncation risk from size + AI-block burial",
    "perplexity": "crawler allowed; weak on Reddit/YouTube signal per framework",
    "bing_copilot": "not independently tested this pass"
  }
}
```

## Files referenced

- `c:\Users\PC\Desktop\Discounts_Engine\seo\audits\www.dealpulseksa.com-audit\homepage-render.json` (pre-existing in this audit folder, re-read this pass)
- `Claude_Memory/zid_affiliate_channel.md` — source for the confirmed Zid click-attribution fact
- `Claude_Memory/owned_audience_reality.md`, `Claude_Memory/seo_owned_channels_pivot.md`, `Claude_Memory/domain_authority_plan.md`, `Claude_Memory/seo_audit_tools_trust.md` — source for §4's brand-signal context (memory, not fresh measurement)
- `Claude_Memory/feedback_prefer_codes_over_tracking_links.md` — existing site principle that recommendation #1 operationalizes for the AI-facing export specifically

---

## [2026-08-11] Follow-up: Page-Level Citability Deep-Dive — /calendar

**Scope note:** this section audits `https://www.dealpulseksa.com/calendar`
specifically, not the whole domain. It builds on figures already measured
and handed to this pass rather than re-deriving them: 2,030 words, H1
"مواعيد التخفيضات في السعودية 2026", 18 H2s / 12 seasons, 10 FAQ H3s, 5
JSON-LD blocks (Organization graph, WebPage, BreadcrumbList, ItemList with
12 items, FAQPage with 10 Q&A), the confirmed zero-mention gap on
وزارة التجارة / mc.gov.sa / ترخيص / رخصة / نظام التخفيضات, and the page's
GSC performance (CTR 2.04% vs 0.25% site-wide on /store, 529 impressions
last 7 days — best-performing page on the site).

**Method / honesty flag:** content was retrieved this pass via `WebFetch`
(a small-model summarization pass over the fetched HTML), not via
`render_page.py`'s `extracted_text` (trafilatura) field as the skill
prescribes — that script was not found in this repo or on this machine this
session (`find` for `render_page.py` returned nothing under the project or
common install paths). The word counts below are therefore **directionally
accurate, not word-perfect** — they are counted with Python `str.split()` on
the exact strings WebFetch returned, but that text passed through one extra
summarization layer before reaching this analysis. It also returned 6 of
the 10 FAQ H3s (likely truncated by its own output budget, not a page
defect). Treat the passage-level claims below as a strong first pass;
re-verify with a raw HTML/trafilatura fetch before treating any single word
count as final.

### 1. Passage-level citability — named passages, quotable vs. not

**Quotable as standalone answers (self-contained, no missing subject, specific):**

| Passage (verbatim) | Words | Why it's citable |
|---|---|---|
| FAQ — "متى تبدأ التخفيضات في السعودية؟" → "لا يوجد موعد واحد؛ السنة فيها عدة مواسم تشمل تصفيات يناير والعيدان ورمضان والعودة للمدارس والعيدين والجمعة البيضاء في نوفمبر." | 20 | **This H3 is a near-verbatim match to the exact target query in this brief.** Question-and-answer are both self-contained; no pronoun or preceding-paragraph dependency. This is the single most important passage on the page for the stated goal. |
| FAQ — "هل تواريخ رمضان والعيدين ثابتة كل سنة؟" → "لا؛ رمضان والعيدان تتبع التقويم الهجري فتتقدّم نحو 11 يوماً كل سنة محددة برؤية الهلال." | 15 | Short, but carries a precise quantified claim ("نحو 11 يوماً كل سنة") — GEO literature on citation behavior consistently finds models will lift a short passage verbatim specifically *because* it contains a precise number, even under the 134–167-word target. |
| Hijri-date disclaimer: "⚠️ مواسم رمضان والعيدين تتبع التقويم الهجري وتُحدَّد برؤية الهلال، لذا تواريخها هنا تقديرية لسنة 2026." | 15 | Fully self-contained caveat, doesn't require page context, and is the kind of honest hedge that (per this task's constraints) should be preserved, not removed — it is itself a citable trust signal, not a weakness. |
| FAQ — "متى الجمعة البيضاء (وايت فرايداي) في السعودية؟" → "آخر جمعة من نوفمبر، ويليها «سايبر مندَي» يوم الإثنين، أضخم موسم تسوق أونلاين." | 13 | Self-contained, names both events, no antecedent needed. |

**Not reliably quotable as-is (context-dependent or too imprecise):**

| Passage pattern | Example | Problem |
|---|---|---|
| Season-body fragments under each H2 | '"23 سبتمبر" يشمل كل الفئات خاصة الإلكترونيات والأزياء والمطاعم والسيارات.' (10 words) | **The subject is missing from the sentence itself.** The season name ("اليوم الوطني السعودي") lives only in the H2 heading above it, not restated in the body. If a chunker/extractor lifts this line without its heading (a real risk — many RAG pipelines split on paragraph, not heading+paragraph pairs), the quote becomes "September 23 covers all categories" with no referent. This same pattern repeats across all ~12 season blocks — it is a structural pattern, not a one-off. |
| Broad/imprecise ranges | "موسم الرياض" → "أكتوبر حتى مارس" (a 6-month span) | Too wide to serve a "when does X start" query with confidence; reads as a category description, not a date answer. Lower priority to fix than the missing-subject issue above, since Riyadh Season is not the target query, but worth noting as a pattern. |
| Hedged/approximate season dates | "رمضان" → "يبدأ ~18 فبراير (تقديري)"، "عيد الفطر" → "~20 مارس (تقديري)" | Correctly hedged (this is the right call per the Hijri caveat, not a defect) — but the "~" and "تقديري" markers mean these specific lines are weaker verbatim-quote candidates than the fixed-date entries (National Day, White Friday), since a model is less likely to state an approximate figure with the same confidence as a fixed one. This is an acceptable tradeoff for honesty, flagged here only so it's not mistaken for a fixable defect. |

**Bottom line:** the page already contains one near-perfect passage for the
exact target query (the "متى تبدأ التخفيضات" FAQ pair), but at 20 words it
is far short of the 134–167-word optimal range documented elsewhere on this
domain's AI block (§3 above), and the 12 season-summary blocks — the page's
main body content — carry a repeated structural flaw (missing subject) that
caps their standalone quotability regardless of length.

### 2. Does the missing mc.gov.sa anchor hurt citability specifically?

**Two different mechanisms, and they should not be conflated.** Google's
ranking algorithm and an AI assistant's citation decision are not the same
process:

- **Google ranking** rewards the *page* for topical authority signals
  (backlinks, corroborating internal/external links, E-E-A-T). A missing
  outbound citation to a primary source is one signal among hundreds, and
  its ranking impact is diffuse and hard to isolate from everything else a
  higher-ranking competitor is also doing better.
- **AI citation** (ChatGPT/Perplexity/AI Overviews deciding what to quote
  or link) leans more heavily, per available reporting on RAG-style
  synthesis, on whether a passage's factual claim can be corroborated
  against a source the model already trusts. A page that names and links a
  primary regulator directly gives the model an explicit corroboration
  anchor for date-sensitive claims — exactly the kind of claim this page is
  built around.

**Honest verdict: likely helps, magnitude unclear.** There is no controlled
public study (that this pass can point to) quantifying "adding one
government citation changes AI-citation odds by X%." What can be said with
more confidence is the *shape* of the gap: the page's 12 shopping seasons
(back-to-school mid-Aug–mid-Sept, National Day Sept 23, Riyadh Season
Oct–March) already fall inside — or straddle — the window the task brief
attributes to competitor pages as the Ministry of Commerce's officially
declared 2026 discount season (1 Aug–31 Oct). That figure comes from the
task brief, not from a live mc.gov.sa fetch performed this pass — **it was
not independently re-verified this session**, and government-declared
windows can change year to year, so it must be confirmed against the live
mc.gov.sa page before publishing, not copied from this brief.

There is also a real conceptual distinction the page currently erases: the
12 "shopping seasons" listed here are informal, marketing-driven retail
events, while "نظام التخفيضات" (the Discount Regulations) is a *separate*,
legally binding framework under which the Ministry of Commerce declares
specific registered discount windows merchants must comply with. A user (or
an assistant) asking "متى تبدأ التخفيضات في السعودية" may mean either sense
of "تخفيضات" — informal shopping season, or the regulated discount period —
and the page currently only answers the first. Naming and citing the
regulatory sense, clearly distinguished from the shopping-calendar sense,
closes a real content gap and gives assistants a second, authoritative
citation point — but whether that specific addition *causes* more citations
is not something this pass can prove, only argue is directionally sound.

### 3. FAQPage schema after Google's May 2026 rich-result retirement — still useful for AI extraction?

Separating what's confirmed from what's inference/vendor claim, as instructed:

- **Confirmed (structural fact, not a claim about outcomes):** JSON-LD
  `FAQPage` markup gives any machine parser — including an LLM ingestion
  pipeline that chooses to read structured data — an unambiguous,
  pre-segmented list of question/answer pairs. That is strictly less
  ambiguous than inferring Q&A boundaries from HTML heading+paragraph pairs,
  where (per §1 above) a chunker can lose the subject/heading association.
  This is true regardless of whether Google displays a rich result for it.
- **Vendor claim / unproven (do not present as fact):** the common GEO-tooling
  claim that "FAQPage schema improves AI citation rate" has no public,
  controlled benchmark behind it that this pass can point to. It is a
  plausible mechanism, not a measured one — no DataForSEO or other citation
  tool was invoked this session to test it directly on this page.
- **Inference this pass is willing to stand behind:** since Google's rich
  result for FAQPage is retired, the *only* remaining consumer of this
  markup is likely other machine readers — including AI crawlers/browsing
  tools that parse structured data preferentially when present. That does
  not prove it moves citation odds, but it means the schema now has a single
  clear purpose (AI/machine extraction) rather than a dual one (SERP
  decoration + extraction), and it costs nothing to keep since it is already
  built and validated. Whether Bing (which powers Copilot) still renders FAQ
  rich results was not checked this pass — flagged as unverified, not
  assumed either way.

**Recommendation on this point specifically:** keep the schema as-is
(zero cost, plausible upside, no confirmed downside); do not invest further
engineering effort expanding it purely on the unproven "schema → citation"
claim — spend that effort on the content-level fixes in §4 instead, which
rest on more defensible mechanisms (self-containment, primary-source
corroboration).

### 4. Three ranked, concrete changes for "متى تبدأ التخفيضات في السعودية"

1. **Expand the exact-match FAQ answer itself — highest priority, lowest
   effort.** The H3 "متى تبدأ التخفيضات في السعودية؟" is already a
   near-verbatim match to the target query (§1). Its current answer is 20
   words; grow it toward the 134–167-word target by folding in the specific
   date ranges already documented elsewhere on the page (back-to-school
   mid-Aug–mid-Sept, National Day Sept 23, White Friday last Friday of
   November + Cyber Monday, 12.12, January end-of-season, June–mid-July
   summer) into one self-contained paragraph that does not require the
   reader to consult the H2 list above it. This is a copy edit against
   content that already exists on the page — no new research required.
   *Effort: Low.*
2. **Add a clearly-labeled, distinct mention of the official Ministry of
   Commerce discount season** ("موسم تخفيضات [year] الرسمي" per نظام
   التخفيضات), explicitly separated from the 12 informal shopping seasons,
   with a citation link to mc.gov.sa. The exact current window must be
   pulled live from mc.gov.sa before publishing — it was not independently
   re-verified this session and should not be copied from this brief's
   figure without checking it is still current. This closes the one
   confirmed content gap competitors already have, and gives assistants a
   primary-source anchor for a date-sensitive claim. *Effort: Low–Medium
   (one verification step + one new paragraph + one citation link, no
   engineering).*
3. **Fix the missing-subject pattern across the 12 season blocks** by
   rewriting each from a date+category fragment into one full sentence that
   restates the season name inline — e.g. replace '"23 سبتمبر" يشمل كل
   الفئات خاصة الإلكترونيات...' with 'يوم الوطني السعودي (23 سبتمبر) يشمل
   تخفيضات في كل الفئات خاصة الإلكترونيات والأزياء والمطاعم والسيارات.' This
   raises the baseline citability of the page's main body (not just the FAQ)
   for every season-specific query, not only the one named in this brief,
   and removes the dependency on a chunker preserving heading+body pairing.
   *Effort: Medium — 12 short rewrites, pure content work, no engineering.*

None of these three recommend adding freshness/verification claims the site
cannot back — #2 is a real, checkable citation to an external authority
(not a fabricated signal), and the Hijri estimate caveat is left untouched
by design, per this task's own instruction that it is a deliberate trust
signal worth preserving.
