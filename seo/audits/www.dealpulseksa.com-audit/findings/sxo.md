# SXO / Search-Experience Audit — www.dealpulseksa.com

**Method:** Read the Arabic SERPs backwards for the three queries the site's store-page template is actually built to compete for: `كوبون خصم نون`, `كود خصم نمشي`, `كوبونات خصم السعودية` — plus a targeted query on the flagged zero-click page, `كوبون خصم Bellas بيلا السعودية`. For the two winning competitor URLs I inspected structure directly via fetch (word count, code count, schema-adjacent UI signals) rather than guessing from titles alone. No `render_page.py` re-fetch of dealpulseksa's own pages was run this session — the target-page facts below are the already-measured figures handed to this audit (`content.md`'s live-measured store-page sample) plus the GSC-reported Bellas numbers; re-deriving them would have burned the tool-call budget without adding new evidence.

**This is the primary finding of the whole audit — lead with it.**

---

## The headline answer

**The store-page format is the RIGHT page type, executed thinly. It is not a page-type mismatch.**

Evidence: all three head-term SERPs are monopolized by the exact same page type dealpulseksa already publishes — a single-store coupon/promo-code page. Zero listicles, zero "best coupon sites 2026" roundups, zero retailer-native pages beat them into the top slots I inspected. If this were a page-type mismatch, the fix would be "build a different template." It isn't — the fix is "make the existing template deep enough to compete," which is a narrower, cheaper, and more mechanical fix than a template redesign.

The **Bellas** page is a separate, second failure mode layered on top of the same template: **entity ambiguity**, not thin content. That one needs a different fix (disambiguation in title/meta), not more words.

---

## 1. SERP inspection — what wins for the site's actual keyword targets

### `كوبون خصم نون` (coupon discount Noon)
Top results, all coupon-aggregator store pages: `otlobcoupon.com/store/nooncouponsegypt-310.html`, `couponwafir.com/store/كود-خصم-نون-noon/`, `couponwafy.com/store/noon-44.html`, `e5smley.com/store/noon`, plus a Facebook page for the same niche. **Page type consensus: single-store coupon page, 100% of inspected results.**

### `كود خصم نمشي` (Namshi discount code)
Top results: `couponzil.com/store/namshi-discount-code/`, `namshidiscountcode.com` (a dedicated single-purpose domain), `couponava.com/store/كوبون-نمشي/`, `codekhasm.com/store/namshi-نمشي/`, `e5smley.com/store/namshi`. **Same page type again, 100% of inspected results.** Note `namshidiscountcode.com` — a whole domain built around one brand's coupon intent, which is the depth-of-commitment ceiling this niche rewards.

### `كوبونات خصم السعودية` (Saudi discount coupons — the broad/hub query)
Top results shift to homepage/hub-level competitors, not individual store pages: `coupon.sa` (dedicated Saudi coupon site), `coponsa.com`, `coupoonat.com`, `almotasuq.com`, plus two coupon apps (`Saudi Coupons` on App Store and Google Play) and `sdcappsa.com`. **Consensus: coupon-portal homepage/hub, not a single-store page** — confirming the store-page template is correctly scoped to brand-level queries (`نون`, `نمشي`) and should not be the page competing for this broader head term; that's a homepage/hub job, which is a separate finding from the store-page depth gap below.

### Structural depth of the two winning store pages I opened directly
| Signal | `e5smley.com/store/noon` | `couponwafy.com/store/noon-44.html` | dealpulseksa `/store/سويتر` (measured in `content.md`) |
|---|---|---|---|
| Word count | ~15,000+ words | ~3,500-4,000 words | **63 words** |
| Codes shown | 60+ codes | 149 total, 8 featured | **1 code** |
| Copy-code UI | "إنسخ الكود الآن" buttons | "نسخ الكود" buttons | prose only, no button |
| Expiry dates | Yes, per-code ("فعال حتى 30/12/2026") | Not per-code | None |
| Live usage/social-proof | "تم الإستخدام: 11,338 مرة" | "استخدام اليوم: 95", "آخر استخدام: منذ 2 د" | None |
| Verified/trust badge | Implied by usage stats | Explicit "موثّق" badge + 4.1★/10 reviews | None |
| FAQ / guide content | Extensive ("طريقة استخدام كود خصم نون", shipping, payment, authenticity) | Extensive FAQ + store history + related stores | Two Q&As, 63 words total |
| Schema (per `content.md`, dealpulseksa side; competitor schema not independently confirmed this session) | not verified | not verified | **Organization + BreadcrumbList only — no Offer, no FAQPage** despite the page literally being an FAQ with a code |

The gap is not "wrong shape," it's **magnitude**: dealpulseksa's store page is 63 words carrying one code with zero trust signals, competing against pages carrying 60-149 codes, live usage timestamps, verified badges, and star ratings — a 55x-to-240x content-depth gap in the same template slot.

---

## 2. Second, distinct failure mode: the Bellas entity-ambiguity case

Searching `كوبون خصم Bellas بيلا السعودية` does not return one dominant "Bella" brand — it returns **at least four unrelated Saudi/regional businesses that all use "بيلا"**: a hair-products store (`belllaa.com`), an evening-dress brand (`Oro Bella`, `code5sm.com/store/oro-bella/`, `wferly.com/store/oro-bella/`), a sandals/shoe brand (`Bella Sandy`, `allcouponat.com`, `wferly.com`), and a homeware store (`Bella Stores`, `bella-sa.com`). None of these is obviously "the" Bella; the name is a generic transliteration collision, not a distinctive brand token.

This directly explains the measured GSC pattern: **398 impressions, average position 5.7, zero clicks.** The page is getting matched and shown for a query token that is genuinely ambiguous in the SERP — a user searching "بيلا" cannot tell from a position-5-6 snippet whether dealpulseksa's result is *their* Bella (hair? dresses? shoes? home goods?) without a title/meta that names the product category explicitly. Faced with that uncertainty next to 4+ competing "Bella" results that do disambiguate in their titles (`أورو بيلا`, `بيلا ساندي`), the rational click goes to whichever snippet names the actual category. High impressions + zero clicks at a mediocre-but-visible position is the signature of a **SERP snippet that fails to disambiguate a generic-name entity**, not of a content-depth problem — this store page could hit 500 words and it would not fix a title that doesn't say what kind of "Bella" this is.

**Fix implication for Bellas specifically:** rewrite title tag and meta description to include the product category (e.g. "كود خصم بيلا [category] السعودية" naming what the store actually sells), not "add more words to the page body." This is a title/meta fix, cheap, and testable within one indexing cycle — flag as the fastest win in this whole audit.

---

## 3. Third, distinct failure mode: blog articles at position 1-4 with 1-2 impressions

This is **not** a SERP-execution problem and should not be diagnosed with the same fix as the store pages above. Per `content.md`'s independent sample, the one blog article inspected had no visible AI-slop markers (specific voice, explicit affiliate disclosure, correctly nested `BlogPosting`+`ItemList` schema). Ranking position 1-4 with only 1-2 impressions is the signature of **near-zero real search volume for the exact query targeted**, not of weak content — Google does not typically hand out top-4 rankings on high-quality SERPs to thin content; it hands out top-4 rankings on *empty* SERPs (no real competition because nobody searches the term). This is a keyword-selection/demand problem for the blog cohort, separate from both the store-page depth gap and the Bellas ambiguity case. Do not spend store-page-style "add more words" effort here — the content is already adequate; the targeting isn't.

---

## 4. Why `/calendar` is the one pattern that earns clicks

`/calendar` is not competing in the same arena as the store-page queries above. There is no equivalent of `e5smley.com`'s 15,000-word single-purpose competitor for a Saudi seasonal-sales calendar query — the competitive field for "مواعيد التخفيضات في السعودية"-type queries is thinner and less commoditized than "كود خصم [national retailer]." Per `content.md`, the calendar page carries the richest schema of any sampled page type (5 JSON-LD blocks) and an honest, specific disclosure (Hijri-calendar date-uncertainty caveat) — exactly the kind of first-hand, non-generic signal the store-page template is missing. `/calendar` succeeds because it picked a page type where DealPulse's actual differentiation (honest curation, no fake precision) is a competitive edge, whereas the store-page template picked a page type where the site is competing on raw depth against domains that have published 15,000 words per brand and lost.

---

## 5. SXO Gap Score — store-page template (0-100, separate from SEO Health Score)

| Dimension | Score | Evidence |
|---|---|---|
| Page Type (0-15) | **14/15** | Confirmed aligned to SERP consensus for brand-level queries (§1) — this is not where the gap is |
| Content Depth (0-15) | **1/15** | 63 words vs. 3,500-15,000+ words on inspected competitors; 1 code vs. 8-149 codes shown |
| UX Signals (0-15) | **2/15** | No copy-button UI evidenced in the rendered prose (per `content.md`), no expiry countdown, no usage/freshness ticker that every inspected competitor carries |
| Schema (0-15) | **3/15** | Organization + BreadcrumbList only (measured); missing Offer and FAQPage despite the page literally being an FAQ containing a code — already flagged in `content.md` as the single highest-confidence fix available |
| Media (0-15) | **2/15** | No store logo/imagery confirmed in the extracted text (competitors show store logo + category imagery) |
| Authority (0-15) | **3/15** | No verified badge, no star rating, no review count — every inspected competitor carries at least one of these |
| Freshness (0-10) | **1/10** | No "last used X minutes ago" or per-code expiry date; competitors show live, ticking freshness signals that both build user trust and give Google a reason to re-crawl |
| **Total** | **26/100** | Low-confidence directionally (n=1 target page, per `content.md`'s own caveat), but the gap pattern is consistent across all 3 head-term SERPs inspected — not a fluke of one query |

---

## 6. User stories (cite the specific SERP signal that generated each)

1. **"Is this code still active?"** — generated by every competitor's expiry date / "آخر استخدام: منذ 2 د" signal (couponwafy.com). Consideration stage. dealpulseksa's page has zero freshness signal to answer this — a user cannot tell if `TZ3F` still works without clicking through and testing it.
2. **"Is this a real/trustworthy coupon site?"** — generated by couponwafy.com's "موثّق" badge + 4.1★/10 reviews. Awareness/trust stage. dealpulseksa carries no third-party trust marker on the page itself.
3. **"Does this store have more than one code, in case the first one fails?"** — generated by e5smley.com/couponwafy.com showing 8-149 codes vs. dealpulseksa's 1. Decision stage — a user bouncing off a failed single code has nowhere else to go on the page.
4. **"Which 'Bella' is this?"** — generated specifically by the fragmented multi-brand SERP in §2. Awareness stage, unique to ambiguous-name stores; the fix is title/meta disambiguation, not page depth.
5. **"How do I actually redeem this?"** — the one story dealpulseksa's page already answers (the 3-step redemption FAQ, per `content.md`) — keep this, it's a genuine strength shared with the competitor FAQ sections.

---

## 7. Recommendations, ranked by evidence strength and the "right type, thin execution" verdict

1. **(Highest confidence — do first) Add `Offer` + `FAQPage` schema to `/store/[slug]`.** Already flagged in `content.md` as a pure schema-authoring task (the code and merchant are already in the prose). Directly closes part of the Schema dimension gap above.
2. **(High confidence, mechanical, scalable) Expand the store-page template to show multiple live codes per store where the catalog supports it, with a visible "last verified" or "last used" timestamp per code.** This is the single largest measured gap (63 words / 1 code vs. 3,500-15,000 words / 8-149 codes) and it is a template change, not a per-page hand-write — one fix propagates across every `/store/[slug]` URL in the sitemap.
3. **(Cheap, fast, isolated) Fix the Bellas title/meta to name the product category explicitly** (and audit the sitemap for any other store names that collide with unrelated Saudi/regional brands — "بيلا" is unlikely to be the only generic-name collision in the catalog). This is a snippet-disambiguation fix, testable in one indexing cycle, independent of the depth work in #2.
4. **(Separate workstream, do not merge with #1-3) Audit blog-cohort keyword targeting, not blog content quality**, per `content.md`'s hypothesis test — the 1-2 impression pattern at position 1-4 points at zero-demand keyword selection, and no amount of store-page-style depth work fixes that.
5. **(Longer-horizon, White-Hat) Where a "verified" or usage-count claim cannot be made truthfully (no real user-verification pipeline exists), do not fabricate one** — per this repo's white-hat wall, fake usage counters or fake review scores are not an option even though every winning competitor displays them. The legitimate substitute is a genuinely dated "last checked" timestamp tied to real catalog-update runs, which DealPulse can support without fabrication.

---

## Cross-skill handoffs

- Schema gap (Offer/FAQPage missing on store pages) → `/seo schema` for generation, coordinated with `content.md`'s identical finding (do not duplicate work, one ticket).
- Thin store-page content at scale (hundreds of `/store/[slug]` URLs per sitemap) → `/seo page` for a page-level audit of the template once depth work in recommendation #2 is scoped.
- Blog keyword-targeting mismatch → `/seo content` for a deeper keyword-demand pass on the 710/764 zero-click cohort; this SXO audit only confirms the *symptom pattern* (good position, near-zero impressions), it does not re-derive keyword demand data.

---

## Limitations

- Target-page facts (63-word store page, Organization+BreadcrumbList-only schema, Bellas GSC numbers) were **not re-fetched this session** — they are the already-measured figures supplied to this audit and cross-referenced against `content.md`'s independent live measurement of the same store-page sample. If those upstream numbers are stale, this audit's comparison table inherits that staleness.
- Only 2 competitor URLs were opened in full for structural detail (`e5smley.com/store/noon`, `couponwafy.com/store/noon-44.html`); the remaining competitor domains named in §1 are cited from SERP title/snippet only, not independently opened — page-type classification for those is snippet-level confidence, not fetch-level confidence.
- Competitor schema markup (Offer/FAQPage/AggregateRating on their side) was **not independently confirmed via raw HTML/JSON-LD inspection** — the depth comparison in §1 rests on visible on-page UI signals (usage counters, badges, code counts), not on a structured-data diff. The dealpulseksa side of that comparison (Organization+BreadcrumbList only) is high-confidence per `content.md`'s live measurement; the competitor side's *schema* (as opposed to visible content) is inferred, not measured.
- No AI Overview / featured-snippet presence was recorded for the three head-term SERPs (WebSearch results returned as ranked links + an AI summary, not a raw SERP screenshot) — SERP-feature analysis (§2 of the standard SXO method) is therefore incomplete for this audit.
- Sample size on the Bellas entity-collision hypothesis is one query variant; a fuller check would search the exact store name as it appears in dealpulseksa's own title tag (not fetched this session) to confirm the collision is real for the precise query users type, not just for the generic "بيلا" term used here.

---

## Structured summary (for `audit-data.json` ingestion)

```json
{
  "category": "search_experience",
  "url_scope": "https://www.dealpulseksa.com",
  "primary_finding": "store_page_right_type_thin_execution",
  "mismatch_severity": "ALIGNED (page type) / CRITICAL (content depth + trust signals)",
  "sxo_gap_score": 26,
  "sxo_gap_score_confidence": "low — n=1 target page, pattern consistent across 3 SERPs inspected",
  "serp_evidence": [
    {"query": "كوبون خصم نون", "dominant_type": "single_store_coupon_page", "consensus_pct": 100, "competitors": ["otlobcoupon.com", "couponwafir.com", "couponwafy.com", "e5smley.com"]},
    {"query": "كود خصم نمشي", "dominant_type": "single_store_coupon_page", "consensus_pct": 100, "competitors": ["couponzil.com", "namshidiscountcode.com", "couponava.com", "codekhasm.com", "e5smley.com"]},
    {"query": "كوبونات خصم السعودية", "dominant_type": "coupon_portal_hub", "consensus_pct": 100, "competitors": ["coupon.sa", "coponsa.com", "coupoonat.com", "almotasuq.com", "sdcappsa.com"]},
    {"query": "كوبون خصم Bellas بيلا السعودية", "dominant_type": "fragmented_multi_entity", "finding": "entity_ambiguity_not_content_gap", "competitors": ["belllaa.com", "code5sm.com/store/oro-bella", "allcouponat.com", "bella-sa.com"]}
  ],
  "depth_comparison": {
    "target_word_count": 63,
    "target_codes_shown": 1,
    "competitor_word_count_range": [3500, 15000],
    "competitor_codes_shown_range": [8, 149],
    "target_schema": ["Organization", "BreadcrumbList"],
    "target_missing_schema": ["Offer", "FAQPage"]
  },
  "distinct_failure_modes": [
    {"page": "store_template", "cause": "content_depth_and_trust_signal_gap", "fix_type": "template_expansion"},
    {"page": "Bellas_store", "cause": "entity_name_ambiguity_in_serp", "fix_type": "title_meta_disambiguation"},
    {"page": "blog_cohort_710_of_764", "cause": "zero_demand_keyword_targeting", "fix_type": "keyword_demand_audit_not_content_rewrite"},
    {"page": "calendar", "cause": "n/a_this_pattern_works", "fix_type": "extend_pattern_to_other_hub_queries"}
  ]
}
```
