# Technical SEO Audit — www.dealpulseksa.com

Date: 2026-08-10
Scope: crawlability, indexability, canonicals, redirects, URL structure, JS rendering, IndexNow.
Pre-measured by other agents (not re-verified here): Next.js/Vercel SSR, homepage 200, canonical host www with apex 308→www on `/`, `/robots.txt`, `/sitemap.xml`, full security-header set, PageSpeed mobile 0.95, sitemap.xml (1748 URLs, flat urlset), schema audited separately.

## Technical Score: 78/100

---

## 1. Crawlability — PASS (robots.txt), WATCH (headless rendering risk)

**robots.txt** (`https://www.dealpulseksa.com/robots.txt`, HTTP 200, fetched live):
```
User-Agent: *
Allow: /
Disallow: /account
Disallow: /login
Disallow: /register
Disallow: /forgot-password
Disallow: /api/
Host: https://www.dealpulseksa.com
Sitemap: https://www.dealpulseksa.com/sitemap.xml
```
Repeated identically (all `Allow: /` + same 4 disallows) for 15 named AI-crawler tokens: GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, anthropic-ai, Claude-Web, PerplexityBot, Perplexity-User, Google-Extended, CCBot, Applebot-Extended, cohere-ai, Bytespider, DuckAssistBot, Meta-ExternalAgent.

- **Nothing valuable is blocked.** The 4 disallowed paths (`/account`, `/login`, `/register`, `/forgot-password`, `/api/`) are all non-indexable utility/auth routes — correct to exclude. No blanket `Disallow: /` on any UA. No disallow on `/store/`, `/c/`, `/category/`, `/blog/`.
- `Sitemap:` directive present and points to the live 1748-URL sitemap. **Severity: none — passing.**
- `Host:` directive is a legacy Yandex-only field with no effect on Google/Bing; harmless but not doing anything for the other engines. **Severity: Low / informational.**
- No `X-Robots-Tag` header on the robots.txt response itself, and none found on homepage or sitemap.xml responses (checked live headers) — no header-level crawl block. **Severity: none.**

**Headless-Chromium rendering failure (flagged by the render agent as `net::ERR_FAILED`)** — investigated:
- Ruled out: **not a User-Agent string block.** `curl` with the literal UA string `HeadlessChrome/120.0.0.0 Safari/537.36` returns HTTP 200 with full 327,502-byte HTML, identical headers to a normal browser UA. A plain-Chrome UA with no `sec-ch-ua`/`sec-fetch-*` headers also returns 200.
- Ruled out: **not application-level bot detection.** `C:\Users\PC\Desktop\dealpulseksa-web\next.config.mjs` has only a `headers()` block (the known CSP/HSTS/etc. security headers) — no middleware.ts, no `vercel.json`, and `package.json` carries no bot-management dependency (`botid`, `arcjet`, custom firewall SDK — only `@vercel/analytics`). The app code contains no bot-fingerprinting logic.
- **Working conclusion:** since curl (raw HTTP/TLS) succeeds and the same Playwright/headless-Chromium binary succeeds against `example.com`, the failure is most consistent with a **platform-level control on Vercel's edge** (Vercel Firewall "Attack Challenge Mode" or automated Bot Protection, which is a dashboard toggle, not repo code, and fingerprints TLS/HTTP2 client behavior rather than the UA header) rejecting the connection before an HTTP response is even generated. This is a hypothesis based on process of elimination, not a confirmed root cause — **it requires checking the Vercel project's Firewall/Security tab directly**, which is outside this audit's fetch access.
- **Why this matters for SEO, not just for this audit's tooling:** Google's, Bing's, and most third-party crawlers' JS-rendering fetchers are themselves headless-Chromium-based. If the edge control that is blocking this session's Playwright is fingerprinting at the TLS/connection layer (rather than a UA allowlist that already excludes known-good crawler UAs), there is a real risk it also degrades or blocks legitimate rendering crawlers — which would not show up in `curl`-based audits (including most of this one) because curl never triggers it.
- **Recommendation (Critical, verify-then-act):** In the Vercel dashboard, check Firewall / Attack Challenge Mode / Bot Protection settings for the project. If enabled, confirm it allowlists Googlebot, Bingbot, and other declared crawler ranges (Vercel's bot management typically does this by IP/ASN, not UA string, so it should already be safe — but this must be confirmed, not assumed). Cross-check via Google Search Console's URL Inspection "Live Test" (uses Google's real rendering service) on a `/store/*` and `/c/*` URL to confirm Googlebot itself is not affected. If GSC's live test also fails to render, this is a Critical indexability issue; if it renders fine, downgrade to Low/informational (tooling-specific, not a real crawler risk).

## 2. Indexability — PASS (canonicals/meta robots), MEDIUM (cache-control scope)

Live-fetched (`curl`, real HTML + response headers) one URL per template from the sitemap:

| Template | URL tested | Canonical tag | Meta robots | X-Robots-Tag header |
|---|---|---|---|---|
| Home `/` | `https://www.dealpulseksa.com/` | (not re-checked, pre-verified) | — | none observed |
| `/store/*` | `.../store/%D9%85%D8%AA%D8%B1%D9%88%20%D8%A7%D9%84%D8%A8%D8%B1%D8%A7%D8%B2%D9%8A%D9%84` | self-referencing, exact match, `www` host | `index, follow` | none |
| `/c/*` | `.../c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-vperfumes-2026` | self-referencing, exact match, `www` host | `index, follow` | none |
| `/category/*` | `.../category/%D8%AC%D9%85%D8%A7%D9%84%20%D9%88%D8%B9%D9%86%D8%A7%D9%8A%D8%A9%20%D8%B4%D8%AE%D8%B5%D9%8A%D8%A9` | self-referencing, exact match, `www` host | `index, follow` | none |
| `/blog/*` | `.../blog/perfume-brands-celebrity-saudi-arabia` | self-referencing, exact match, `www` host | `index, follow` | none |

- **All four templates self-canonicalize correctly to the `www` host with no cross-template or cross-host mismatch, and carry `index, follow` with no `X-Robots-Tag` header override anywhere.** This is a clean pass — no noindex traps, no canonical drift. **Severity: none.**
- One canonical-hygiene nit: the canonical `<link>` on `/store/*` and `/category/*` **repeats the raw-space percent-encoding** (`%20`) rather than normalizing to the encoded form a canonicalized/hyphenated URL would use — see §4 URL Structure for the underlying cause and scope. Not a correctness bug (canonical does match the actual served URL exactly, which is what matters to Google), but it means the canonical is anchoring search engines to an already-suboptimal URL rather than a cleaner one. **Severity: Low.**

### Cache-Control / no-store scope — broader than previously flagged

The known finding was "store template sends `private, no-cache, no-store, max-age=0, must-revalidate` on a public page." Live headers on all four templates show this **also applies to `/category/*`**, but not to `/c/*` or `/blog/*`:

| Template | `Cache-Control` header (live) |
|---|---|
| `/store/*` | `private, no-cache, no-store, max-age=0, must-revalidate` |
| `/category/*` | `private, no-cache, no-store, max-age=0, must-revalidate` |
| `/c/*` | `public, max-age=0, must-revalidate` |
| `/blog/*` | `public, max-age=0, must-revalidate` |
| Home `/` | `public, max-age=0, must-revalidate` |
| `/sitemap.xml` | `public, max-age=0, must-revalidate` |

- **Impact:** `no-store` forbids any HTTP cache (CDN edge, browser, or intermediary) from storing the response at all. Combined with `private`, it also tells any cache the response is not shareable across users. This is correct for personalized/authenticated pages and wrong for `/store/*` and `/category/*`, which are public, canonicalized, sitemap-listed pages meant for shared crawl/cache reuse. Practical effects: (a) Vercel's own edge cache cannot serve these pages from cache — every hit (including every crawler re-fetch) round-trips to origin, adding latency and origin load that public pages don't need; (b) it signals "do not cache this" to any CDN/proxy in the path, which is the opposite of what a store/category listing page — content that changes on a coupon-refresh cadence, not per-request — should send.
- **Scope confirmed live:** affects both `/store/*` (53 URLs in sitemap) and `/category/*` (59 URLs in sitemap) = **112 of 1748 sitemap URLs (6.4%)**. `/c/*` (61 URLs) and `/blog/*` (1583 URLs) are unaffected and correctly cacheable.
- **Severity: High.** Not a hard indexability blocker (Google still crawls/indexes these fine per the canonical/meta-robots check above), but it is a self-inflicted performance and origin-load tax on exactly the two templates (store profile pages + category hubs) that carry the highest link equity in the site's internal linking.
- **Recommendation:** In the Next.js route handlers/pages for `/store/[slug]` and `/category/[slug]`, replace the `no-store`/`private` cache directive with a `public, max-age=0, s-maxage=<N>, stale-while-revalidate=<M>` pattern (matching whatever revalidation strategy `/c/*` and `/blog/*` already use, since those are already correct) — most likely this is an accidental `cache: 'no-store'` fetch option or a `Cache-Control` override left over from when these pages carried per-user state (e.g. favorites/auth-gated UI) that no longer applies to the public route.

## 3. Redirects — PASS

- Apex → `www`: confirmed single-hop 308 on all three tested paths, no chain:
  - `http(s)://dealpulseksa.com/` → `308` → `Location: https://www.dealpulseksa.com/`
  - `https://dealpulseksa.com/robots.txt` → `308` → `Location: https://www.dealpulseksa.com/robots.txt`
  - `https://dealpulseksa.com/sitemap.xml` → `308` → `Location: https://www.dealpulseksa.com/sitemap.xml`
- All three land directly on the final `www` URL in one hop (no secondary redirect observed). 308 is the correct permanent, method-preserving status. **Severity: none — passing.**

## 4. URL Structure — MEDIUM (raw spaces in slugs, majority of two templates)

Counted live against the fetched sitemap.xml (1748 URLs):

| Template | Total URLs | URLs with raw space (`%20`) in slug | % affected |
|---|---|---|---|
| `/store/*` | 53 | 31 | 58% |
| `/category/*` | 59 | 14 | 24% |
| `/c/*` | 61 | 0 | 0% |
| `/blog/*` | 1583 | not counted (ASCII slugs by convention, e.g. `perfume-brands-celebrity-saudi-arabia`) | — |

Example: `https://www.dealpulseksa.com/store/%D9%85%D8%AA%D8%B1%D9%88%20%D8%A7%D9%84%D8%A8%D8%B1%D8%A7%D8%B2%D9%8A%D9%84` decodes to `مترو البرازيل` — the store name with its literal space character percent-encoded (`%20`), not converted to a hyphen. `/c/*` slugs, by contrast, are properly hyphenated even where Arabic is present (`%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-vperfumes-2026` → `كود-خصم-vperfumes-2026`).

- **Real SEO impact of the Arabic percent-encoding itself: none.** Google has handled UTF-8/percent-encoded URLs correctly for over a decade; rendered SERP snippets decode back to readable Arabic. This is not a ranking or crawl issue and should not be "fixed" by transliterating to Latin/English slugs.
- **Real SEO impact of the *raw space* specifically: Medium, not cosmetic.** A literal space in a slug is a URL-hygiene defect independent of the Arabic-encoding question: (a) it is fragile across systems that don't uniformly percent-encode spaces (some log parsers, some link-sharing contexts, copy-paste into old tools that use `+` for space in query strings vs `%20` in paths will corrupt it); (b) it produces a less clean, less shareable URL than the hyphenated `/c/*` pattern already used elsewhere on the same site, so the fix pattern already exists in the codebase; (c) it's inconsistent within the site's own information architecture — a visitor/bot sees hyphenated slugs on `/c/*` and space-encoded slugs on `/store/*` and `/category/*`, which reads as an unfinished implementation.
- **Recommendation:** Normalize `/store/*` and `/category/*` slug generation to hyphenate spaces (matching the `/c/*` slugify function already in use), 301-redirect the old space-encoded URLs to the new hyphenated ones, and update `sitemap.xml` + all internal links accordingly. Given 45 of 1748 URLs (31 store + 14 category) are affected, this is a bounded, scriptable fix, not a re-platforming effort.

## 5. Mobile — PASS

- Viewport meta tag (homepage, live-fetched): `<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5"/>` — correct `width=device-width`/`initial-scale=1`, and `maximum-scale=5` (rather than `1` or `user-scalable=no`) means pinch-zoom is not disabled, which is a common mobile-accessibility/UX anti-pattern this site avoids. **Severity: none.**
- `<html lang="ar" dir="rtl">` confirmed on the live homepage — correct RTL declaration for Arabic-only content. **Severity: none.**
- PageSpeed mobile 0.95 (pre-measured, not re-verified here) is consistent with no additional mobile red flags found in source.

## 6. Core Web Vitals — no new source-level issues found

Not re-measured beyond what was already flagged (PageSpeed mobile 0.95, and the `no-store` cache issue in §2 which is a performance concern more than a CWV-metric concern — it does not directly move LCP/INP/CLS but does add avoidable origin round-trip latency on `/store/*` and `/category/*`).

## 7. Structured Data — out of scope

Per task instructions, schema is audited separately; skipped here.

## 8. JavaScript Rendering — SSR confirmed (pre-verified), see §1 for the headless-rendering risk

`is_spa=false`, SSR via Next.js on Vercel — already confirmed by another agent, not re-verified. The only open JS-rendering question this audit adds is the headless-Chromium connection failure investigated in §1, which is a crawlability/tooling-access risk, not a rendering-architecture problem — the HTML is fully server-rendered when a request succeeds (confirmed by the raw `curl` HTML pulled for every template in §2, which contains fully populated content, not an empty SPA shell).

## 9. IndexNow Protocol — not verified this pass

Not tested in this session (no IndexNow key file or submission endpoint fetched). Flag as **untested**, not pass/fail — a follow-up check should fetch `https://www.dealpulseksa.com/<indexnow-key>.txt` and confirm it matches a key registered with Bing/Yandex, per the existing `Claude_Memory/seo_bulk_reindex_ops.md` operational notes (IndexNow bulk-push already in use per that memory file, so the key almost certainly exists — this just wasn't re-confirmed live in this session).

---

## Prioritized Issues

**Critical**
1. Headless-Chromium connection failure (`net::ERR_FAILED`) against the production domain — UA-string blocking and application-level bot detection both ruled out live; most consistent with a Vercel edge/Firewall control. Needs direct confirmation via Vercel dashboard Firewall settings + a GSC "Live Test" render check on `/store/*` and `/c/*` before downgrading — if it also affects Googlebot's renderer, this blocks correct indexing of JS-dependent content (there is none currently, since SSR is confirmed, but it would block any future client-rendered enhancement and could affect rich-result eligibility checks that use headless rendering).

**High**
2. `Cache-Control: private, no-cache, no-store, ...` on `/category/*` in addition to the already-known `/store/*` — 112/1748 sitemap URLs (6.4%), covering the two highest-link-equity templates. Fix: switch to `public, max-age=0, s-maxage=<N>, stale-while-revalidate` matching the `/c/*`/`/blog/*` pattern already correct in the same codebase.

**Medium**
3. Raw-space (`%20`) percent-encoded slugs on 31/53 `/store/*` (58%) and 14/59 `/category/*` (24%) URLs — inconsistent with the properly hyphenated `/c/*` pattern on the same site. No ranking impact from the Arabic encoding itself; the space character is the actual defect. Fix: hyphenate + 301 old→new, bounded to 45 URLs.

**Low**
4. Canonical tags on `/store/*`/`/category/*` repeat the raw-space encoding (correct relative to the served URL, but inherits the URL-structure defect above — resolves itself once #3 is fixed).
5. `Host:` directive in robots.txt is Yandex-only legacy syntax with no effect on Google/Bing — harmless, no action required.

**Informational / Untested**
6. IndexNow key file not verified live this session — confirm `/​<key>.txt` still resolves and matches the registered key.

---

## Files/paths referenced
- `c:\Users\PC\Desktop\dealpulseksa-web\next.config.mjs` (headers() block — no middleware/bot-detection code found)
- `c:\Users\PC\Desktop\dealpulseksa-web\package.json` (no bot-management dependency)
- Live URLs cited inline above (robots.txt, sitemap.xml, one `/store/*`, one `/c/*`, one `/category/*`, one `/blog/*`, apex domain on `/`, `/robots.txt`, `/sitemap.xml`)
