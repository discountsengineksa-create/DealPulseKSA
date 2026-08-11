# Performance / Core Web Vitals — www.dealpulseksa.com
## Before/After: `/store/*` and `/category/*` prerendering fix (shipped 2026-08-10)

**Data source: LAB ONLY (PageSpeed Insights v5 / Lighthouse, mobile strategy, single run per URL,
2026-08-11).** CrUX field data does **not exist** for this domain — the CrUX API returns
`404 chrome ux report data not found`, meaning the site is below Google's minimum-traffic sampling
threshold. This is not a tooling fault; it is not retried. Every number below is a single synthetic
Lighthouse run, not a 28-day real-user distribution, and Google's 75th-percentile pass/fail
evaluation **cannot be performed** on this domain until CrUX starts returning data. INP specifically
has **no measurement at all** in this report — Lighthouse lab runs do not simulate real user
interactions, so no lab INP number exists either; Total Blocking Time (TBT) is used below only as a
rough interactivity-risk proxy, not as INP.

**What changed (confirmed live, both sides measured):** `/store/*` and `/category/*` moved from
`x-vercel-cache: MISS` + `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate`
to `x-vercel-cache: PRERENDER` + `Cache-Control: public, max-age=0, must-revalidate`, by adding
`generateStaticParams` to both dynamic segments and removing a `searchParams` read from the store
page's server component. These two templates carry 7,508 of the site's 12,957 monthly impressions
(58%).

## Pages measured (4/4 requested, mobile strategy)

| Page | Perf score | LCP (lab) | TTFB (lab, `server-response-time`) | TBT (lab, weak INP-risk proxy) | CLS (lab) | FCP (lab) |
|---|---|---|---|---|---|---|
| `/store/بيلاس` (fixed template — priority) | 86 | **4.13 s** — POOR (score 0.46) | 4 ms | 43 ms | 0 — good | 0.9 s |
| `/category/تطبيقات` (fixed template) | 97 | **2.63 s** — needs improvement (score 0.87) | 4 ms | 0 ms | 0 — good | 0.9 s |
| `/calendar` (content focus, unaffected by fix) | 98 | **2.40 s** — good (score 0.91) | 14 ms | 20.5 ms | 0 — good | 1.0 s |
| `/` homepage (unaffected by fix, comparison point) | 94 | **3.00 s** — needs improvement (score 0.78) | 9 ms | 0 ms | 0 — good | 1.4 s |

Homepage baseline on record: PSI mobile performance score **0.95** (measured 2026-08-10, before
the fix). Today's homepage re-run scores **0.94** — a 1-point difference is single-run Lighthouse
variance, not a signal; the homepage template was not touched by this fix and should be flat.

## The before/after comparison (the actual question this report answers)

The previous lab audit of this site (same repo, same `performance.md`, dated before the fix)
measured the `/store/*` template — a **different individual store page**, `/store/سويتر`, not
`/store/بيلاس` — under the old `private, no-cache, no-store` header:

| Metric | `/store/سويتر` — BEFORE (no-store, old audit) | `/store/بيلاس` — AFTER (PRERENDER, this run) |
|---|---|---|
| Perf score | 93 | 86 |
| LCP | 3.2 s (score 0.74) | 4.13 s (score 0.46) |
| TTFB (`server-response-time`) | 11 ms | 4 ms |
| TBT | 60 ms | 43 ms |

**Caveat that matters more than the numbers:** these are two *different store pages*, not the same
URL re-measured. `/category/*` has no prior lab run at all (the earlier audit tested `/store`,
`/calendar`, `/blog` — not `/category`), so there is no before/after pair for the category template
either. This report is the first lab measurement ever taken of `/category/*`, and the store-template
comparison is confounded by page-specific content (different Cloudinary story-media asset, different
byte weight) rather than being a clean A/B of the same page.

**TTFB**: dropped from 11 ms to 4 ms on the store template. Both numbers are within single-digit
milliseconds — this is the range where Lighthouse/PSI run-to-run noise (different test timestamp,
possibly different Google test-runner region) is as large as the delta itself. PSI's test vantage
point is already close to Vercel's edge network regardless of cache status, so a lab TTFB of
11 ms even on the *uncached* `no-store` path was never going to expose the real cost of that
header — the cost of `no-store` shows up as **origin compute load and dollar cost at scale**, which
a single lab probe close to the edge cannot see. **Lab TTFB data does not support a measurable
before/after speed claim** — it was already fast before, and it is (immeasurably) faster now.

**LCP**: got *worse* in this measurement (3.2 s → 4.13 s, crossing from "needs improvement" into
"poor"). This is real data and is reported honestly rather than discarded — but it is not
attributable to the caching change. The store template's LCP element is a Cloudinary
`story_media/theme_*.png` asset that differs per store; `/store/بيلاس`'s version is heavier and,
per the `lcp-discovery-insight` audit (failed, score 0, on both the old and the new run), is still
not eagerly discoverable from the initial HTML — the same root cause flagged in the prior audit
(see Bottlenecks below) is still unfixed and is the far larger lever on this template than the
cache-header change.

## Verdict

**The caching change is a CDN/origin-compute/cost win, not a measured user-visible speed win.**
Every visitor to `/store/*` and `/category/*` now gets served from Vercel's edge (`PRERENDER`)
instead of triggering a fresh SSR execution on every request — that is real, confirmed by the
header change alone, and it matters at 7,508 impressions/month of scale for origin compute cost and
resilience under load. But nothing in this lab data shows an LCP or TTFB improvement large enough to
separate from noise: TTFB was already sub-15ms in Lighthouse's near-edge test vantage before the
fix, and LCP on the one template with a same-template before/after comparison moved in the wrong
direction (confounded by page content, not the cache header). **Do not report this as an LCP win.**
Report it as: fixed a scaling/cost problem, with real-world speed impact for users on slower
connections/higher network RTT than PSI's test location — currently **unverifiable** because CrUX
has no field data for this domain. Re-run this exact comparison once CrUX starts returning records;
that is the only data source that can settle the user-facing-speed question definitively.

## Bottlenecks identified (unrelated to the caching fix — carried over / still open)

1. **`lcp-discovery-insight` fails on both fixed templates** (`/store/بيلاس` and `/category/تطبيقات`,
   score 0 on both) — the LCP candidate image is not eagerly discoverable / not preloaded from
   initial HTML. This is the same defect flagged in the pre-fix audit and is unaffected by the
   cache-header change. **This is the actual lever to move LCP on these templates**, not caching.
   Add `fetchpriority="high"` and ensure the LCP image (Cloudinary story-theme asset on `/store`,
   equivalent hero/card image on `/category`) ships in the server-rendered HTML with no lazy-load.

2. **Render-blocking CSS** — identical single stylesheet
   (`_next/static/css/b1b905cecca16531.css`, 14.6 KB) on all four pages measured, costing
   130–187 ms of estimated LCP savings per the `render-blocking-insight` audit on every page. Same
   finding as the prior audit — still unaddressed, template-wide, cheap fix once done in one place.

3. **Legacy JavaScript** — identical 12,141 wasted bytes from
   `_next/static/chunks/255-98a0bdaa30757bda.js` on all four pages. Same finding as prior audit.

4. **Homepage and `/calendar` LCP sit in "needs improvement"/at-the-edge-of-good** (3.0 s and
   2.4 s respectively) — neither was touched by this fix and neither regressed; not a priority for
   this before/after pass but worth folding into the `lcp-discovery-insight` fix above since the
   root cause (LCP image discoverability) is shared across templates.

## Recommendations, prioritized

1. **Do not claim a CWV win from this deploy in any stakeholder-facing report.** Report it correctly
   as an infrastructure/cost fix (origin compute reduction at 7,508 impressions/month scale) with an
   *unverified* user-facing speed effect, pending CrUX field data.
2. **Fix `lcp-discovery-insight` on `/store/*` and `/category/*`** — highest-impact, verifiable-today
   lever on the templates that matter most (58% of impressions). Expected impact: should recover
   the store template from "poor" (4.1 s) toward "needs improvement" or better, independent of caching.
3. **Re-run this exact 4-URL PSI comparison after CrUX field data becomes available** for this
   domain (currently 404 — below sampling threshold) — that is the only source that can confirm
   whether real Saudi users on slower networks see a TTFB/LCP improvement the lab test cannot detect.
4. Inline/split the shared 14.6 KB render-blocking stylesheet and drop the 12 KB of legacy JS
   transpilation — both template-wide, low-effort, apply once.
