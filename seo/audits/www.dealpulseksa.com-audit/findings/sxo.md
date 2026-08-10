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

**لحظات القهوة** (43 impr. pos 9.1, 0 clicks) — top results: the merchant's own site and app (`coffeemoments.net` / `ecoffeemoments.net`), and five different owned social accounts (Instagram, TikTok, X, YouTube, Facebook). This one is especially telling: Coffee Moments is a **B2B beverage-ingredients supplier** (coffee/tea/syrup agent for Molinari, Dilmah, Torani), not a consumer retailer with a "discount code" shopping habit at all. A user typing this bare name is looking for the company, not a coupon.

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
