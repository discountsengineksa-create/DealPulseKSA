# SXO / Search-Experience Audit — www.dealpulseksa.com (CORRECTED)

## Correction notice — replaces the previous version of this file

The prior run of this audit searched **"بيلا"** (a truncated, wrong keyword) instead of the store's actual name **"بيلاس"**, found four unrelated Saudi brands colliding on that wrong token, and concluded "entity ambiguity" with a title-rewrite fix. That was built on a typo, not on the real query. Real Google Search Console data (28 days, pulled live 2026-08-10, property `https://www.dealpulseksa.com/`) has since shown the actual pattern, and this version is built on GSC's real query list plus fresh SERP inspection of those exact queries. **Do not reuse the "four Saudi brands" / "entity ambiguity" framing — it is retracted.**

**Method note (limitation, stated up front):** the search tool used for SERP inspection is US-based and not Saudi-localized. Results below are directionally useful (what page types and entities occupy a query's result set globally/from a non-KSA vantage point) but the exact rank order, local-pack presence, and any Saudi-specific SERP features (e.g. `اشتري الآن` shopping carousels, Saudi map-pack results) cannot be confirmed from here. This caps confidence on all three findings below to "structural pattern," not "exact SERP screenshot."

---

## GSC facts this audit is built on (measured, not modeled)

**Totals (28d):** 7,609 impressions · 34 clicks · CTR 0.45% · 944 of 961 query-page rows have zero clicks.

**By position band:**
| Band | Impr. | Clicks | CTR |
|---|---|---|---|
| 1-3 | 171 | 19 | 11.1% |
| 4-10 | 1,765 | 7 | 0.40% ← biggest single loss |
| 11-20 | 866 | 2 | 0.23% |
| 21-50 | 2,684 | 3 | 0.11% |
| 51+ | 2,123 | 3 | 0.14% |

**By page segment:**
| Segment | Impr. | Clicks | CTR |
|---|---|---|---|
| `/store` | 5,643 (74% of site total) | 7 | 0.12% |
| `/blog` | 680 | 2 | 0.29% |
| `/category` | 554 | 2 | 0.36% |
| `/calendar` | 360 | 4 | **1.11% (9x /store)** |
| `/c` | 248 | 0 | 0% |
| homepage | 28 | 17 | 60.7% (brand searches, "نبض الصفقات") |

---

## Headline finding

**`/store` is not one failure mode, it's two, and they need opposite fixes.** A large share of its 5,643 impressions come from **bare store-name queries where the intent is navigational-to-the-merchant** (بيلاس, المخملية, لحظات القهوة, عذيه) — Google is matching the page correctly, but a third-party coupon aggregator is structurally not what these searchers want, so no on-page optimization converts that click. Separately, a smaller set of **genuinely commercial queries** (كود خصم مرايا, كود خصم موقع هواوي) sit at winnable positions (4.9 and 10) against real coupon-aggregator competition — that subset is the actual optimization opportunity, and even there the sample sizes are mostly too thin to diagnose with confidence except in the one case (هواوي) with enough impressions to say something concrete. `/calendar`'s 9x CTR confirms the pattern: it wins because it competes on informational queries against guides and government sources, not against merchant identity or a saturated coupon-code field.

---

## 1. Bare store-name queries: navigational-to-merchant, not a content problem

Searched the three bare-name queries directly (non-KSA vantage point, stated above).

**بيلاس** (207 impr., pos 5.5, 0 clicks) — top results are: the merchant's own site (`chrisbella-sa.com`, "كريسبيلا صارت بيلاس" — literally the brand announcing its own rename), the brand's Instagram (`@bellas.s3`), and unrelated Pilates services. **No coupon-aggregator result appeared in the visible set at all.** The SERP is dominated by first-party brand identity, not commerce comparison.

**المخملية** (55 impr. pos 10 + 51 impr. pos 8.3 — two spellings, same brand) — top results: the merchant's own site (`almokhmalih.sa`, an abaya/jalabiya designer brand), plus unrelated uses of the word (a plant genus, a Wattpad novel, a perfume line). Again, **first-party brand site dominates**, no coupon competitor visible.

**لحظات القهوة** (43 impr. pos 9.1, 0 clicks) — top results: the merchant's own site and app (`coffeemoments.net` / `ecoffeemoments.net`), and five different owned social accounts (Instagram, TikTok, X, YouTube, Facebook). ~~This one is especially telling: Coffee Moments is a **B2B beverage-ingredients supplier** (coffee/tea/syrup agent for Molinari, Dilmah, Torani), not a consumer retailer with a "discount code" shopping habit at all.~~ **RETRACTED 2026-08-11 — this agent got the business model wrong.** The owner verified it is an ordinary consumer retailer, and our own Salla data agrees: **2 orders, 365.04 SAR, 10% commission** (`Claude_Memory/salla_proven_converters.md`). The agent saw `coffeemoments.net` in the SERP and projected that site's business model onto the merchant without checking. The navigational-intent conclusion still holds on its own evidence (merchant site + five owned social accounts occupy the SERP) — a user typing the bare name is looking for the company, not a coupon. The reason is the intent, not the business model.

**Verdict:** across all three, the SERP a bare store name produces is owned-brand-property-dominated (official site + social), not commerce/comparison-dominated. That is the signature of navigational intent. A coupon aggregator is not a snippet-wording problem away from winning that click — it is competing for a slot the query isn't asking for. Recommend **abandoning on-page optimization pursuit of pure bare-name queries** (no title rewrite, no added content will convert this — the previous audit's title-rewrite recommendation for this class of query should not be actioned). The only legitimate lever left is: does the query carry an explicit commercial modifier ("كود خصم", "كوبون")? If yes, it moves into the class below and is worth a look. If the bare name alone is what's driving the impression, it is out of scope for SXO optimization.

---

## 2. Commercial-intent queries at page-one positions: one too-small-to-conclude, one genuinely losing

**كود خصم مرايا** (30 impr., pos 4.9, 0 clicks) — Search results for "مرايا" collapse toward **"ميرايا" (Miraaya)**, an Iraqi cosmetics/beauty retailer, not a Saudi brand — a sign the query token itself may be ambiguous or normalized oddly by the search stack, but from a non-localized vantage point this cannot be confirmed as what a Saudi searcher actually sees. What can be said with confidence is the sample size: **30 impressions over 28 days is roughly 1/day.** At an industry-typical CTR for position ~5 (roughly 4-7%), expected clicks over that window land around 1-2 — getting zero is well within normal Poisson variance for a base rate this low. **Verdict: too small a sample to diagnose a snippet or ranking problem here.** Do not treat this as a proven loss; flag it for re-check once impressions accumulate (e.g. after 90+ days or once volume triples).

**كود خصم موقع هواوي** (86 impr., pos 10, 0 clicks) — this is the higher-confidence case, both because the sample is ~3x larger and because the SERP is fully visible and saturated: the top results are Huawei's own official coupon-support page **plus seven distinct third-party coupon-aggregator domains** all targeting this exact query (`couponzil.com`, `allcouponat.com`, `goldencouponzz.com`, `couponava.com`, `couponwafy.com`, `codekhasm.com`, `couponswadi.com`). Position 10 is the last slot on page one — the tail end of the 4-10 band, which is already the site's single biggest impression-to-click loss (1,765 impr. → 7 clicks, 0.40% CTR sitewide). **This is losing to something specific: a crowded field of established, single-purpose coupon domains outranking dealpulseksa for the exact same intent.** The query type is correctly matched (commercial, coupon-seeking, right page type) — the problem is competitive position, not intent mismatch. At position 10, even average-for-position CTR (~2-3%) would predict roughly 2 clicks from 86 impressions; getting zero is a real (if still modest-n) signal that this specific listing is being skipped in favor of the competitors above it, not proof of total unwinnability.

**Distinction to hold onto:** مرايا = insufficient data, don't act yet. هواوي = real competitive displacement in a page type the site is correctly positioned for — this is the actual "optimize the store template" opportunity, not the bare-name queries in §1.

---

## 3. What makes `/calendar` winnable — and how to extend it deliberately

`/calendar`'s winning queries (`متى تبدأ التخفيضات في السعودية` 24 impr. pos 9.0 → 1 click; `مواعيد التخفيضات في السعودية` 11 impr. pos 8.1 → 1 click; `مواعيد التخفيضات العالمية` 1 impr. pos 6.0 → 1 click) share a structural trait the `/store` queries don't: **the SERP for "when do sales start" has no single dominant merchant or brand to compete against.** Inspecting `متى تبدأ التخفيضات في السعودية` directly: the result set is a mix of a **government source** (`mc.gov.sa`, Ministry of Commerce official sale-season announcement), **news outlets** (`maaal.com`, `ajel.sa`), and **independent guide/calendar content** (`qyubic.com` "دليل أفضل مواسم العروض", `allcouponat.com` "جدول التخفيضات السنوي", `me-jeddah.com`). `dealpulseksa.com/calendar` itself appeared directly in this result set, ranked alongside these mixed-authority sources — competing as a peer, not as an outsider trying to unseat a merchant's own homepage.

Three concrete traits define this winnable query class, extractable and repeatable:
1. **No entity monopoly** — unlike a store name (§1) or a hyper-specific coupon code (§2), "when do sales happen" has no single canonical answer-owner. A calendar/guide page is a legitimate contender by default.
2. **Broad, evergreen, TOFU phrasing** — "متى", "مواعيد", "جدول" (when/schedule/calendar) signal informational intent that content hubs (not stores, not aggregators) are expected to answer. This matches the page type Google already shows for the query.
3. **Mixed-authority competitive set, not a saturated single-purpose niche** — government + news + guides is a shallower, less commoditized field than the seven-deep coupon-aggregator wall found for هواوي in §2. Less competition per slot.

**How to extend deliberately:** identify other genuinely broad, entity-free, schedule/guide-shaped queries (season names, "أفضل وقت للشراء", occasion-specific "متى يبدأ" variants — the existing `seasonal_events` table and occasion pages already in the codebase are the natural source list) and build/expand calendar-adjacent hub content for them, rather than trying to force the `/store` template to win queries (§1) where a merchant's own identity structurally outranks any third-party aggregator.

---

## SXO Gap Score — revised, split by query class (not one blended score)

| Query class | Page type used | Winnable in principle? | Evidence |
|---|---|---|---|
| Bare store-name (بيلاس, المخملية, لحظات القهوة, عذيه) | `/store` | **No — navigational intent, abandon pursuit** | §1: SERPs owned by merchant's own site + social, zero coupon competitors visible |
| Commercial + code query, thin sample (مرايا) | `/store` | Undetermined | §2: n=30, statistically inconclusive |
| Commercial + code query, real sample (هواوي) | `/store` | **Yes, but currently losing on position** | §2: pos 10 vs. 7 direct competitor coupon domains |
| Broad informational/schedule queries | `/calendar` | **Yes, and already winning** | §3: 9x CTR vs. `/store`, peer-ranked with gov/news/guide sources |

Dimension scoring for the one class actually worth optimizing (`/store` commercial-intent subset, هواوي-type queries):

| Dimension | Score | Evidence |
|---|---|---|
| Page Type (0-15) | 13/15 | Correctly matched for the commercial subset; the score is not 15 because a meaningful share of `/store`'s 5,643 impressions are the unwinnable navigational subset in §1, meaning the template is being served against queries it cannot win at all, diluting the segment's real CTR |
| Content Depth / UX / Schema / Media / Authority / Freshness | Not re-scored this session | Already measured against live competitor structure in this audit's prior content-depth pass (see `content.md` for the 63-word / 1-code / no-Offer-schema findings); those measurements are unaffected by this correction and still stand — this file's correction is scoped to query-intent classification, not to the depth/schema/UX gap |

---

## Recommendations, ranked

1. **(Do first, zero cost) Stop treating bare store-name impressions as an SXO opportunity.** Do not rewrite titles/meta for بيلاس, المخملية, لحظات القهوة, عذيه chasing CTR — the intent is navigational-to-merchant and structurally unwinnable by a coupon aggregator. Redirect that effort.
2. **(Real opportunity, needs scale not just this page) For the هواوي-class queries — commercial intent, position 4-10, real competitor field visible — the fix is competitive depth/authority on the `/store` template**, consistent with this audit's separate content-depth findings (see `content.md`): more codes shown, visible freshness/last-checked signals, `Offer`+`FAQPage` schema. This is the queries this template should actually be optimized for.
3. **(Wait, don't act) مرايا-class queries with n<50 impressions** — re-check after volume accumulates (90-day window) before concluding anything about snippet performance.
4. **(Extend deliberately) Build more `/calendar`-adjacent broad/schedule content** using the three traits in §3 (no entity monopoly, TOFU phrasing, mixed-authority competitive field) as the selection filter for which new queries are worth targeting — this is the site's only currently-proven winnable pattern.
5. **White-Hat constraint, unchanged:** do not add fabricated usage counters or review scores to close the Authority/Freshness gap on `/store` pages — no verification pipeline exists to back them. The legitimate substitute is a real "last checked" timestamp tied to actual catalog-update runs.

---

## Cross-skill handoffs

- Schema gap (`Offer`/`FAQPage` missing on `/store` pages) → `/seo schema`, coordinated with `content.md`'s identical finding.
- Query-intent segmentation at scale (which of the hundreds of `/store/[slug]` URLs carry navigational-only impressions vs. real commercial-intent impressions) → `/seo content` or a dedicated GSC query-classification pass; this audit only demonstrates the pattern on 5 sampled queries, it does not classify the full 961-row query set.
- `/calendar` pattern extension → `/seo page` once a candidate list of broad/schedule queries is drafted from `seasonal_events`/occasion pages.

---

## Limitations

- **Search tool is US-based, not Saudi-localized.** All SERP inspections in this file (§1-§3) reflect what a non-KSA vantage point returns, not necessarily what a Saudi searcher sees. Rank order, local-pack presence, and Saudi-specific SERP features could not be confirmed. Findings are stated as structural patterns (what entity/page-type dominates a query), which is more robust to this limitation than exact-position claims would be.
- Only 5 of the ~7 flagged queries were directly inspected this session (بيلاس, المخملية, لحظات القهوة, كود خصم مرايا, كود خصم موقع هواوي, متى تبدأ التخفيضات في السعودية) — جولينا and عذيه were named in the brief but not independently searched; the navigational-intent pattern in §1 is inferred to extend to them by analogy (bare Saudi/regional brand name, no commercial modifier), not confirmed by direct inspection.
- Sample sizes throughout are small in absolute terms (single-digit clicks sitewide); statistical claims in §2 use standard CTR-by-position benchmarks as a sanity check, not a formal significance test against dealpulseksa's own historical baseline (insufficient volume exists for that).
- This file corrects query-intent/SERP classification only. The separate content-depth, schema, and UX gap findings from the prior audit pass (word count, code count, missing `Offer`/`FAQPage` schema — documented in `content.md`) were not re-verified this session and are carried forward as still-standing.

---

## Structured summary (for `audit-data.json` ingestion)

```json
{
  "category": "search_experience",
  "url_scope": "https://www.dealpulseksa.com",
  "correction_of_prior_finding": true,
  "prior_finding_retracted": "entity_ambiguity_among_four_saudi_brands_bella_typo",
  "primary_finding": "store_impressions_split_navigational_unwinnable_vs_commercial_winnable",
  "gsc_window_days": 28,
  "gsc_totals": {"impressions": 7609, "clicks": 34, "ctr_pct": 0.45, "zero_click_query_page_rows": 944, "total_query_page_rows": 961},
  "query_classes": [
    {"class": "bare_store_name_navigational", "examples": ["بيلاس", "المخملية", "لحظات القهوة", "عذيه"], "winnable": false, "action": "abandon_optimization_pursuit"},
    {"class": "commercial_code_query_thin_sample", "examples": ["كود خصم مرايا"], "impressions": 30, "position": 4.9, "winnable": "undetermined_insufficient_data"},
    {"class": "commercial_code_query_real_sample", "examples": ["كود خصم موقع هواوي"], "impressions": 86, "position": 10, "winnable": true, "action": "close_competitive_depth_gap", "competitor_count_visible": 7},
    {"class": "broad_informational_schedule", "examples": ["متى تبدأ التخفيضات في السعودية", "مواعيد التخفيضات في السعودية"], "page": "/calendar", "winnable": true, "ctr_pct": 1.11, "vs_store_ctr_pct": 0.12}
  ],
  "limitation_search_tool_not_ksa_localized": true
}
```

---

## 2026-08-10 (addendum) — `/c` is the site's only zero-click page type: cannibalization verdict

**New trigger:** corrected page-level GSC pull (28d, same property, later same day): site total 12,957 impressions / 132 clicks / 1.02% CTR. `/calendar` 1,859/38/2.04% · `/blog` 3,250/50/1.54% (565 pages) · `/category` 815/4/0.49% · `/store` 6,693/17/0.25% (49 pages) · **`/c` 411/0/0.00% (35 pages)**. Note this table's totals are larger than the §GSC-facts table above (7,609/34) because it was pulled later the same day with a rolling 28-day window shifting forward — both are real GSC pulls, not a contradiction, just different snapshot times; page-type ordering and the `/c`-is-worst pattern is consistent across both.

**Method used this session:** `claude-seo run render_page.py --mode auto --json` against 3 live `/c` URLs (Bellas, Vogacloset, Airalo) succeeded (HTTP 200, `mode_used: raw`, Vercel/Next.js SSR headers confirmed real, non-cached-error responses). **Forcing `--mode always` (Playwright) failed on all 4 URLs attempted (2 `/c`, 2 `/store`) with `net::ERR_FAILED` — a tool/network problem on this run, not a site-down signal (the plain `raw` fetch to the same domain succeeded seconds apart with 200s).** This means: **no `/store` page was successfully fetched this session** — the `/store` side of the comparison below relies on (a) the title strings given directly in the task brief, which match the previously-documented pattern in `Claude_Memory/seo_c_store_cannibalization.md`, and (b) this file's own carried-forward `content.md` findings (thin `/store` content, no `Offer`/`FAQPage` schema) — not a fresh fetch. This is a real limitation, disclosed rather than papered over.

### 1. Does cannibalization explain the zero clicks?

**Partially — and the data itself proves it's not the whole story.** Per `Claude_Memory/seo_c_store_cannibalization.md` (fix shipped 2026-08-08, web commit `6425411`), a `duplicatesStorePage()` function already detects `/c` pages whose title reduces (after stripping year/percent/"فعّال"/Latin brand name) to exactly "كود خصم {اسم المتجر}" and sets their canonical to the matching `/store` page — **confirmed live at 19 of 61 published `/c` pages** as of that date.

That fix is doing *something*: the memory file's own count was 61 published `/c` pages; today's GSC breakdown shows only **35** `/c` pages generating *any* impression in the 28-day window. If the 61-page figure is still current (not independently re-counted this session — flagged as an inference, not a live count), that implies roughly **26 pages generate zero impressions at all**, i.e. Google has stopped surfacing them in favor of the canonical `/store` target — the fix working as designed for that subset.

**But the 35 pages that still surface convert at exactly 0%, not just "lower than /store."** That is not what a working canonical alone would predict — `rel=canonical` does not guarantee Google drops a URL from appearing in results (Google frequently still indexes and shows the non-canonical URL, especially early after signal consolidation), so some residual `/c` impressions after a canonical fix is expected. **Zero clicks across all 35, including pages presumably outside the exact-duplicate-title subset the fix targets (i.e. pages the fix deliberately left alone as "differentiated"), means a second, independent problem exists beyond cannibalization: the pages that DO still get shown are not being clicked, which is a snippet/CTR-appeal problem, not just a duplicate-indexing problem.** Verdict: cannibalization is the primary structural cause but not sufficient on its own to explain a flat 0% across the entire remaining set — evidence in §2 below shows why the surviving pages don't convert either.

**Direct rank comparison for the same query, as requested:** could not be observed live this session (no successful fetch/SERP check pairs this specific instance produced a side-by-side rank for one query showing both URL types — WebSearch was not run this addendum given the turn budget; the tool's US-vantage-point limitation, already disclosed above, would apply equally here). This is a genuine gap — flagged, not glossed over. The strongest available evidence for "which one wins" remains the already-documented جولينا case in the memory file: GSC showed a real ranking position (م 8.1, 77 impressions) that the owner's own manual search could not reproduce in 30 results — the memory's own diagnosis is that Google **alternates** between `/store/جولينا` and `/c/كود-خصم-jolina-2026` for the same query, splitting and diluting signal rather than either one consistently winning. That alternation, not a stable "one wins", is the actual mechanism — consistent with why canonical (a soft signal) rather than a 301 (a hard signal) has not fully stopped the split.

### 2. What differs in the SERP-visible layer

**Title/H1, confirmed live (Bellas, fetched this session):** the `/c` page's `extracted_text` (trafilatura-cleaned, boilerplate stripped) opens with the exact string **"كود خصم بيلاس 2026: خصم 15% على مجوهراتك الجديدة!"** — identical to the `<title>` given in the task brief. That means on this page, **title = H1 = opening sentence**, verbatim, with no differentiation between what the SERP snippet shows and what the reader sees first — a templated-thin-content signature. The `/store` title in the same brief, **"كود خصم بيلاس 15% فعّال 2026 | نبض الصفقات"**, carries two things the `/c` title lacks: the word **"فعّال"** (active/currently-valid — the single highest-intent trust cue a coupon searcher scans a snippet for) and the **brand name** ("نبض الصفقات") for source recognition. The `/c` title instead reads as lifestyle marketing copy ("خصم 15% على مجوهراتك الجديدة" — "15% off your new jewelry") with an exclamation mark, closer to an ad headline than a utility answer to "is there a working code."

**Body content, confirmed live (Bellas):** the full `extracted_text` is lifestyle-blog register throughout — "جدّدي إطلالتك بأحدث إكسسوارات ومجوهرات بيلاس الفاخرة" ("refresh your look with Bellas's latest luxury accessories"), "محط الأنظار" ("the center of attention"), "بأسعار لا تُقاوم" ("prices you can't resist") — copywriting voice, not the transactional register ("verified", "last checked", "X uses today") that content.md documented as what wins on `/store`-type templates against competitors.

**Schema, confirmed live (Bellas) — this is the addendum's one genuinely new, counter-intuitive finding:** the `/c` page ships **3 valid JSON-LD blocks, 5,381 bytes total** — `Organization`/`WebSite`/`ContactPoint` (site-wide), **`FAQPage` + `Article` + `Question`/`Answer`** (page-specific), and `BreadcrumbList`. That means **`/c` is not thinner on schema than `/store`** — if anything it appears to carry richer structured data than what this audit's `content.md` pass documented as missing (`Offer`/`FAQPage`) on `/store`. This reframes the diagnosis: **the zero-click problem on `/c` is not an on-page depth/schema deficiency — it is being out-competed for the same intent by a page (`/store`) carrying a more trust-calibrated title, while both pages fight over one shared ranking slot.** (Caveat: `/store`'s own schema could not be directly re-verified this session per the fetch failure above; this claim compares live-measured `/c` schema against the prior audit's `content.md` characterization of `/store`, not a same-session pair.)

### 3. Verdict

**Consolidate `/c` into `/store` — upgrade the existing canonical-tag fix to a 301 redirect for the duplicate-title subset, and fold the differentiated remainder's genuinely useful angles (FAQ content, lifestyle framing) into the `/store` template rather than keeping them as separate competing URLs.**

Justification, numbers-first:
- **35 pages, 411 impressions, 0 clicks, 0.00% CTR — the only page type on the entire site with a flat zero.** Even `/category` (the second-worst segment) converts at 0.49%, `/store` at 0.25%. There is no CTR floor to defend; there is nothing to lose by removing the URL from independent competition.
- **The 2026-08-08 canonical fix is directionally correct but structurally too weak:** `rel=canonical` is a hint Google is free to ignore, and per the memory file's own جولينا case, Google is observed **alternating** between the two URLs rather than converging — meaning the underlying problem (two URLs, one intent, split signal) persists even after the fix for the subset it doesn't fully suppress. A 301 is a directive, not a hint — it removes the second URL from the index entirely and consolidates 100% of any link/impression signal onto `/store`, rather than leaving `/c` "eligible but ignored."
- **Do not pick the reverse (consolidate `/store` into `/c`).** `/store` already carries 6,693 impressions and 17 clicks — 16x the impression volume of `/c` at a non-zero (if weak) CTR — plus it is the page type this audit's §2 above already identified as the one queries with real commercial intent (هواوي-class) actually compete on. `/c` has zero proof of working at all.
- **Do not "differentiate instead."** The memory file already tried the differentiation path for the minority of `/c` pages the fix deliberately left alone (e.g. "متجر ريمان", which does earn a real click on a genuinely different query, "متجر" not "كود خصم") — that pattern only works when the `/c` page answers a *provably different query* from the store page, verified per-page, not as a blanket policy. For the Bellas/Vogacloset/Airalo-type pages sampled this session — same merchant, same "كود خصم X" intent, cosmetic copywriting-vs-utility difference only — there is no different query to defend; they are near-clones of `/store`, not a distinct page type.
- **Do not drop `/c` entirely without redirecting.** These pages hold whatever residual crawl equity/impression history they've accumulated (411 impressions of visibility exist); a bare removal (404/noindex-and-abandon) throws that away. A 301 into the matching `/store` slug preserves and consolidates it instead.

**Scope of the 301 recommendation:** apply it to the same `duplicatesStorePage()`-detected subset already identified by the existing fix (title reduces to literal "كود خصم {store}") — do not blanket-redirect all 61 pages. The handful the memory file already found earning real distinct-query traffic (متجر ريمان-pattern) should be kept and re-optimized as their own page type (informational "about the merchant" / delivery-specific angle), not redirected — but every page in that surviving set should be re-verified against live GSC query data (not assumed) before being spared, since this addendum's 0%-across-all-35 result suggests the safe list may be smaller in practice than the 08-08 audit assumed.

### Limitations (this addendum)

- **No `/store` page was successfully fetched this session** (Playwright `net::ERR_FAILED` on all `--mode always` attempts; `--mode auto` for `/store` was not retried after the Playwright failures, given the 10-turn budget). The `/store` side of the §2 comparison relies on the task brief's given title strings plus this file's own already-standing `content.md` findings, not a fresh same-session fetch — flagged, not disguised as measured.
- **No live head-to-head SERP rank comparison was run this addendum** (§1's direct-request item). WebSearch was not invoked this pass; the جولينا alternation case from the existing memory file is the best available evidence for the mechanism, not a fresh observation.
- **The "61 → 35 pages, ~26 suppressed" arithmetic in §1 combines two different sessions' counts** (memory file dated 2026-08-08, GSC pull dated 2026-08-10) and was not verified by an independent live count of `seo_landing_pages` rows this session — stated as an inference with the gap disclosed, per the zero-fabrication rule.
- Search tool (for any SERP work) remains US-based, not Saudi-localized — same caveat as the rest of this file.
- Only 3 of the 35 live `/c` pages were fetched and inspected (Bellas succeeded and was read in full; Vogacloset and Airalo were fetched successfully in raw mode but not individually parsed for title/schema in this pass given the turn budget — the Bellas findings are presented as representative of the templated pattern, not independently confirmed on all three).

### Structured summary (addendum, for `audit-data.json` ingestion)

```json
{
  "category": "search_experience",
  "url_scope": "https://www.dealpulseksa.com",
  "addendum_date": "2026-08-10",
  "primary_finding": "c_pages_only_zero_click_page_type_sitewide_cannibalization_partial_explanation",
  "gsc_window_days": 28,
  "gsc_totals_later_pull": {"impressions": 12957, "clicks": 132, "ctr_pct": 1.02},
  "segment_ctr": {"calendar_pct": 2.04, "blog_pct": 1.54, "category_pct": 0.49, "store_pct": 0.25, "c_pct": 0.00},
  "c_page_count_with_impressions": 35,
  "c_page_count_published_prior_audit": 61,
  "existing_fix": "rel_canonical_duplicatesStorePage_19_of_61_pages_2026-08-08",
  "fix_sufficiency": "partial_suppresses_impressions_for_some_pages_does_not_explain_zero_ctr_on_survivors",
  "verdict": "consolidate_c_into_store_via_301_upgrade_from_canonical",
  "verdict_scope": "duplicate_title_subset_only_not_blanket_all_61",
  "fetch_failures_this_session": ["playwright_mode_always_net_ERR_FAILED_4_urls", "no_store_page_fetched_live"],
  "confirmed_live_findings": {
    "bellas_c_title_equals_h1_equals_opening_sentence": true,
    "bellas_c_schema_blocks": ["Organization/WebSite/ContactPoint", "FAQPage/Article/Question/Answer", "BreadcrumbList"],
    "bellas_c_tone": "lifestyle_marketing_copy_not_utility_coupon_register"
  },
  "limitation_search_tool_not_ksa_localized": true,
  "limitation_no_store_page_fetched_this_session": true,
  "limitation_no_live_serp_head_to_head_this_addendum": true
}
```
