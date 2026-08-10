C# Performance / Core Web Vitals — www.dealpulseksa.com

**Data source: LAB ONLY (PageSpeed Insights v5 / Lighthouse, mobile).** No field data exists —
CrUX API and CrUX History both returned `403 Client Error: Forbidden` on
`https://chromeuxreport.googleapis.com/v1/records:queryRecord` for every URL tested. This means
the Chrome UX Report API is not enabled on the Google Cloud project that owns the key at
`C:\Users\PC\.config\claude-seo\google-api.json` (PageSpeed Insights API works fine on the same
key — different API, different enablement flag). **Fix:** in that Cloud project, enable
"Chrome UX Report API" in APIs & Services → Library, then re-run
`claude-seo run crux_history.py <url> --json`. Until then, no 75th-percentile real-user figure
can be reported for LCP/INP/CLS on this domain — every number below is a single synthetic
Lighthouse run, not a distribution.

Homepage (out of scope for this pass, already measured previously): performance score 0.95.

## Pages measured (3/3 requested, mobile strategy)

| Page | Perf score | LCP (lab) | TBT (lab, INP proxy) | CLS (lab) | FCP (lab) |
|---|---|---|---|---|---|
| `/store/سويتر` (no-store template) | 93 | **3.2 s** — needs improvement (score 0.74) | 60 ms | 0 — good | 0.9 s |
| `/calendar` | 98 | **2.5 s** — good, at the edge (score 0.90) | 44 ms | 0 — good | 0.9 s |
| `/blog/perfume-brands-celebrity-saudi-arabia` | 79 | **4.5 s** — POOR (score 0.37) | 248 ms | 0 — good | 1.0 s |

CWV pass/fail (lab-only, thresholds from the 2026 table — LCP good ≤2.5s / needs-improvement
2.5–4.0s / poor >4.0s):

- `/store/سويتر`: LCP **needs improvement**, CLS good, INP cannot be measured in lab (TBT 60 ms is a low-risk proxy).
- `/calendar`: LCP **good** but only by 24 ms of margin (2476 ms vs. 2500 ms threshold) — not resilient to any regression. CLS good.
- `/blog/perfume-brands-celebrity-saudi-arabia`: LCP **poor** (4.5 s, nearly double the "good" ceiling). CLS good. TBT 248 ms is the highest of the three pages and sits in Lighthouse's own "needs improvement" TBT band — the strongest lab signal that INP will be elevated on this template.

No page shows any CLS risk (all measured 0.000 exactly) — layout-shift is not a problem on this
site's current templates.

## Bottlenecks identified

### 1. Blog template — LCP 4.5s is the single worst number measured (highest priority)
- Gap between FCP (1.0s) and LCP (4.5s) is **3.5 seconds** — more than double the FCP→LCP gap on
  the other two pages (store: 2.2s, calendar: 1.6s). That gap size, not raw byte weight, is the
  signal something is actively delaying LCP element paint on this template specifically.
- `total-byte-weight` audit lists `https://www.dealpulseksa.com/logo.png` at **102,882 bytes**
  (100 KB) as a directly-requested asset on this page — separate from the correctly-optimized
  `_next/image?url=%2Flogo.png&w=128&q=75` (1,912 bytes, AVIF) that the header nav already uses.
  Something on the blog template (likely `<head>` OG/schema image tag or a raw `<img>` not routed
  through `next/image`) is pulling the unoptimized original PNG.
- **Console error present**: `Error: Minified React error #418` (hydration text mismatch —
  server-rendered HTML doesn't match client render) firing from
  `_next/static/chunks/4bd1b696-c023c6e3521b1417.js`. A hydration mismatch forces React to
  discard the server-rendered subtree and re-render client-side, which is a plausible root cause
  for a 3.5s FCP→LCP gap: the visually-complete paint has to wait for client JS to re-render
  content rather than the already-painted SSR HTML being used as-is.
- `lcp-discovery-insight`-class issue also present on the store page (see below) — worth checking
  whether the blog's LCP element (hero image or first content block) is equally not discoverable
  from the initial HTML.
- TBT 248 ms — 4x the other two pages — with 4 long tasks vs. 2-3 elsewhere; `bootup-time` shows
  517ms total JS execution attributed to the document itself plus 468ms to chunk `255-*.js`.

### 2. Store template — LCP 3.2s + defeated CDN cache (second priority, highest reach)
- `lcp-discovery-insight` audit **failed** (score 0): "Optimize LCP by making the LCP image
  discoverable from the HTML immediately, and avoiding lazy-loading." The only late-loading image
  on this page is the Cloudinary story-theme asset
  (`res.cloudinary.com/.../story_media/theme_*.png`, 33 KB) requested well after the CSS/font
  wave — consistent with it being the LCP candidate and not being eagerly discoverable/preloaded.
- Server response time itself is not the problem in this lab run (11 ms) — but this page is
  served with `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate` on a
  **public** page. That header combination defeats Vercel's CDN/Edge cache entirely: every single
  visitor triggers a full SSR execution on the origin, for what is documented as the
  highest-commercial-intent template on the site (one instance per store, i.e. this cost is paid
  on every store page, not just this one). The 11 ms TTFB seen here is from Lighthouse's own test
  vantage point close to the origin/edge; real Saudi-based users hitting a cold, non-cached SSR
  path will not see 11 ms, and there is currently no CrUX field data available to quantify the
  real-world tax (see CrUX block above). This is a cost/latency risk that scales with traffic and
  cannot be fixed by any front-end optimization — it has to be fixed at the response-header /
  data-revalidation layer (switch to `public, s-maxage=…, stale-while-revalidate=…` and invalidate
  via `revalidatePath`/`revalidateTag` on coupon updates, per the ISR pattern already used
  elsewhere per `website_seo_engine.md`, rather than opting the whole route out of caching).

### 3. Shared across all three pages (lower priority, small but consistent)
- **Render-blocking CSS**: same single stylesheet (`_next/static/css/b1b905cecca16531.css`,
  14.6 KB) blocks first paint on all three pages, costing 140-164 ms of estimated LCP savings on
  each page per the `render-blocking-insight` audit. Candidate for critical-CSS inlining or
  splitting since 70,889 bytes uncompressed serving 14.6 KB compressed suggests most of it is
  unused per-page (`unused-css-rules` diagnostic also fires on all three, though Lighthouse scores
  it 1/1 because the absolute bytes are small — do not ignore just because the audit "passes").
- **Legacy JavaScript**: identical 12,141 wasted bytes on all three pages from
  `_next/static/chunks/255-98a0bdaa30757bda.js` — polyfills/transforms for pre-Baseline browsers
  that are very likely unnecessary. Check the project's browserslist/next.config target.
- **Two preloaded woff2 fonts** (35.6 KB + 32.7 KB = ~68 KB) load consistently in the 290-360ms
  window on every page and do not appear to be blocking FCP (FCP is 0.9-1.0s on all three, in the
  "good" band) — font loading is not currently a CWV problem, no action needed here.
- **CSP allows `unsafe-inline` + host-allowlist `script-src`** — flagged by Lighthouse's
  `csp-xss`/`trusted-types-xss` audits on all three pages. Not a CWV metric, but noted since it
  surfaced on every run; a security-hardening item, not a performance one.

## Recommendations, prioritized by expected CWV impact

1. **Fix the blog template's LCP (4.5s → target <2.5s).** Two concrete, verifiable steps:
   a) find and eliminate the direct 100 KB `/logo.png` request on the blog template — route it
   through `next/image` like the header does (should drop to ~2 KB AVIF), and b) resolve the
   React hydration error #418 (compare server vs. client render output for whatever component is
   mismatching — the fact that this error is unique to the blog template out of the three pages
   tested is the strongest lead). Expected impact: largest single CWV win available — this page
   is currently in the "poor" bucket, the other two are not.

2. **Stop defeating CDN cache on the store template.** Replace
   `private, no-cache, no-store, max-age=0, must-revalidate` with a `public` cache policy plus
   explicit revalidation on write (ISR/`revalidatePath`), scoped to this route only. This does not
   move the lab LCP number much (11 ms TTFB already), but it is the correct fix for real-world TTFB
   at scale on the single highest-commercial-intent template, and it cannot be assessed further
   until the CrUX API is enabled (see fix above) — re-run CrUX after enabling the API to confirm
   real-user TTFB before/after.

3. **Make the LCP image eagerly discoverable on the store template.** Add `fetchpriority="high"`
   and ensure the Cloudinary story-theme image (or whatever resolves as LCP) is present in initial
   server-rendered HTML with no lazy-loading, per the failed `lcp-discovery-insight` audit.
   Expected impact: closes the gap on a page currently sitting just above the "good" LCP threshold.

4. **Inline/split the shared 14.6 KB render-blocking stylesheet.** ~150 ms of estimated savings
   per page across every template on the site (store, calendar, blog all show the identical
   pattern) — cheap, template-wide win once done in one place.

5. **Drop unnecessary legacy-JS transpilation** (~12 KB wasted on every page) by confirming the
   build target excludes polyfills for pre-Baseline browsers. Minor but free once confirmed.

6. **Re-run this audit with CrUX field data once the Chrome UX Report API is enabled** — every
   number in this file is a single lab run; a 75th-percentile field measurement is required before
   any pass/fail CWV verdict can be considered final per Google's evaluation method.
