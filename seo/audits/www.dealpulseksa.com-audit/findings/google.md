# Google SEO API Findings — dealpulseksa.com

**Data source:** Google API (field data) — PageSpeed Insights v5, Chrome UX Report API, Google Search Console API (service account `gsc-indexer@dealpulseksa-aab18.iam.gserviceaccount.com`), Google Indexing API v3.
**Property:** `https://www.dealpulseksa.com/` (service account holds `siteOwner`).
**Audit date:** 2026-08-10.

## Credential Tier

Verified live via `google_auth.py --check --json`:

| Service | Status | Method |
|---|---|---|
| PageSpeed Insights v5 | Available | API key |
| CrUX | Available | API key |
| CrUX History | Available | API key |
| Search Console (query + URL Inspection + sitemaps) | Available | Service account |
| Indexing API v3 | Available | Service account |
| GA4 Data API | **Not available** | No `ga4_property_id` configured |

**Tier 1 (Authenticated) confirmed. Tier 2 not reached** — GA4 property ID is missing from `C:\Users\PC\.config\claude-seo\google-api.json`. No organic-landing-page GA4 cross-check was possible this audit. Recommend adding a `ga4_property_id` if a GA4 property exists for the site, to unlock Tier 2 on the next audit.

## Core Web Vitals (Lab + Field)

| Metric | Result | Rating |
|---|---|---|
| PSI mobile homepage score | 0.95 | Good |
| CrUX field data (origin) | HTTP 404 — "chrome ux report data not found" | No data |
| CrUX field data (homepage URL) | HTTP 404 — "chrome ux report data not found" | No data |

**Closed finding, not a blocker:** the CrUX API itself is working (Tier 1 confirmed above); the site simply does not yet have enough Chrome traffic volume to populate a CrUX bucket, for either the origin or the homepage URL. No CWV field ratings (LCP/INP/CLS) can be reported until organic traffic grows. Lab data (PSI 0.95 mobile) is the only signal available today.

## Search Performance (28-Day GSC Query Report)

Pulled via `gsc_query.py --property https://www.dealpulseksa.com/ --json`, saved at `seo/audits/www.dealpulseksa.com-audit/gsc-28d.json`.

| Metric | Value |
|---|---|
| Total impressions | 7,609 |
| Total clicks | 34 |
| CTR | 0.45% |
| Query-page rows | 961 (944 with zero clicks = 98.2%) |

By template:

| Template | Impressions | Clicks | CTR | Share of impressions |
|---|---|---|---|---|
| `/store` | 5,643 | 7 | 0.12% | 74% |
| `/blog` | 680 | 2 | 0.29% | 9% |
| `/category` | 554 | 2 | 0.36% | 7% |
| `/calendar` | 360 | 4 | 1.1% | 5% |
| homepage | 28 | 17 | 60.7% | <1% |

`/store` dominates impression volume but converts almost none of it to clicks — consistent with pages that are visible in the index but ranking too deep to be clicked. Homepage is the only template with a healthy CTR, on trivially small volume (28 impressions).

**Freshness note:** GSC data carries a 2-3 day reporting lag; the last 1-2 days of any 28-day window are typically incomplete.

## Sitemap Status

Pulled via `gsc_query.py sitemaps --property https://www.dealpulseksa.com/ --json` (live call, this audit):

| Field | Value |
|---|---|
| Sitemap | `https://www.dealpulseksa.com/sitemap.xml` |
| Last submitted | 2026-08-08T15:35:39Z |
| Pending | No |
| Type | web (not a sitemap index) |
| Errors | 0 |
| Warnings | 0 |
| URLs submitted | 1,748 |

**Important API limitation:** the Sitemaps endpoint only reports `submitted` URL counts — it does **not** report how many of those 1,748 URLs are actually indexed. That number can only come from the URL Inspection API, spot-checked below (Google does not expose a bulk "indexed count" for a whole sitemap via any public API). Zero errors/warnings means Google parsed the sitemap cleanly, not that all 1,748 URLs are indexed.

## URL Inspection Sample (7 URLs, one per template)

Pulled via `gsc_inspect.py --batch <7 urls> --site-url https://www.dealpulseksa.com/ --json` (live call, this audit). **5 of 7 succeeded, 2 timed out at the API level** (`URL Inspection API error: The read operation timed out`) — reported as unknown, not treated as a negative indexation signal.

| URL | Verdict | Coverage state | Last crawl | Canonical match (Google vs. declared) | Referring URLs Google recorded |
|---|---|---|---|---|---|
| `/` (homepage) | PASS | Submitted and indexed | 2026-08-09 | Match — `https://www.dealpulseksa.com/` both sides | 3: a blog article, `https://dealpulseksa.com/` (non-www), `/terms` |
| `/calendar` | **ERROR** — request timed out | — | — | — | — |
| `/store/مماز اند بابازر` | **ERROR** — request timed out | — | — | — | — |
| `/c/كود-خصم-airalo-2026` | PASS | Submitted and indexed | 2026-07-13 (28 days stale) | Google canonical present; **user (declared) canonical returned null** | 1: `sitemap.xml/` only |
| `/category/زيوت سيارات` | PASS | Submitted and indexed | 2026-08-04 | Match | 1: a blog article |
| `/blog/perfume-brands-saudi-arabia` | PASS | Submitted and indexed | 2026-08-07 | Match | 1: `sitemap.xml` |
| `/blog/aliexpress-differential-oil-transfer-case-saudi-arabia` | PASS | Submitted and indexed | 2026-07-25 | Match | **0 — no referring URLs recorded** |

All 5 pages that returned a verdict are "Submitted and indexed," robots ALLOWED, indexing ALLOWED, fetch SUCCESSFUL — a genuinely indexed sample across 4 different templates (home, `/c`, `/category`, `/blog`). The two that failed (`/calendar` and `/store`) are unverified, not confirmed-absent — they need a re-run, ideally outside a batch call, since `/store` is the highest-impression template in the whole site (74% of all impressions) and its indexation status is the single most consequential unknown from this audit.

Two items worth flagging from the data actually returned:
1. **`/c/كود-خصم-airalo-2026` has no detectable declared canonical** (`user_canonical: null`) while Google still assigned it a self-canonical. Worth checking whether the `/c/` template renders a `<link rel="canonical">` tag at all — relevant given the known `/c/` vs `/store` cannibalization risk already on file (`seo_c_store_cannibalization.md`).
2. **The AliExpress blog article has zero referring URLs in Google's record** — Google found it through neither the sitemap nor any tracked internal link. This matches the previously logged internal-link orphan issue (`blog_internal_link_deorphan.md`) — it is one live example of it, not a new discovery.

## Sitemap-vs-Impressions Gap: What It Does and Doesn't Show

The question: 1,748 URLs in the sitemap vs. 961 query-page rows in 28 days of GSC data — what does that gap mean?

**What it does NOT mean:** it is not evidence that ~787 URLs are unindexed. A query-page row only appears if that URL received ≥1 impression for at least one query in the 28-day window (and very-low-volume rows can be anonymized out of the query report entirely — see the `totals_complete` caveat already documented for this GSC connector). A URL can be fully indexed and still generate zero rows if it never surfaced in a real search in 28 days.

**What the evidence actually gathered supports:** the 5-URL spot check (n=5, across 4 templates) came back 100% "Submitted and indexed." Combined with the click data — 98.2% of query rows earn zero clicks, and the `/store` template alone (74% of impressions) converts at 0.12% CTR — the pattern is consistent with pages **being indexed and appearing in search results, but ranking too deep (or too irrelevant to the query) to be clicked**, not with Google refusing to index the catalogue. This lines up with the prior finding already on file (`seo_page_portfolio_verdict.md`: 710/764 pages at zero clicks) — the same shape of problem, now confirmed from the indexation side rather than only the clicks side.

**What is still genuinely unknown:** a firm indexed-URL count for the full 1,748-URL sitemap. That requires inspecting a much larger sample than 7 URLs (the API itself timed out on 2 of 7 here, so batches need retry logic and this is rate-limited work, not a one-call answer). If a hard indexation-rate number is needed for the report, it should be flagged to the orchestrator as a follow-up requiring a larger, slower inspection run — not fabricated from this sample.

## Priority Findings

| Priority | Finding | Action |
|---|---|---|
| High | `/store` template — 74% of all site impressions, 0.12% CTR, and its representative URL inspection **timed out** (indexation status unverified for the single highest-volume template) | Re-run URL Inspection on `/store` pages individually (not batched) to get a verdict; separately, investigate why `/store` pages rank deep despite high impression volume — likely a ranking/relevance problem, not indexation |
| Medium | `/c/كود-خصم-airalo-2026` returned no declared canonical (`user_canonical: null`) though Google still self-canonicalized it | Verify the `/c/` template actually renders a `<link rel="canonical">` tag; cross-check against `/store` cannibalization risk already on file |
| Medium | AliExpress blog article has zero Google-recorded referring URLs (orphan) | Already tracked in `blog_internal_link_deorphan.md`; this is a confirmed live instance |
| Low | CrUX has no field data (404 on both origin and homepage) | No action needed yet — insufficient Chrome sample size; revisit once organic traffic grows |
| Low | GA4 not configured — Tier 2 unreached | Add `ga4_property_id` to `google-api.json` if a GA4 property exists, to unlock organic landing-page cross-checks on future audits |

## Report Generation

A PDF report can be generated via `google_report.py --type indexation --data <data.json> --domain www.dealpulseksa.com --format pdf --json` (or `--type full` to combine with PSI/CrUX/GSC data). Not run this pass — offer to generate on request, using the data captured above plus `gsc-28d.json`.
