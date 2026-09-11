# Sitemap Audit — www.dealpulseksa.com

Audited: 2026-08-10. Method: direct `curl` fetch of the live sitemap (no source-code reading — this repo's Next.js `sitemap.ts` was intentionally NOT read).

## 1. Discovery & Format

- `robots.txt` declares: `Sitemap: https://www.dealpulseksa.com/sitemap.xml` — obtained via `curl -s https://www.dealpulseksa.com/robots.txt | grep -i sitemap`. Single directive, one sitemap file.
- `curl -s -o sitemap.xml -w "HTTP_STATUS:%{http_code} SIZE:%{size_download}"` → **HTTP 200, 345,022 bytes (345 KB)**.
- Root element: `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">` — **this is a flat sitemap, NOT a sitemap index** (`grep -o "<sitemap>"` → 0 matches; `grep -o "<sitemapindex"` → 0 matches). So the "fetch up to 3 child sitemaps" step in the brief does not apply — there is only one file, no extrapolation needed anywhere below; every count is a direct measurement.
- XML declares `<?xml version="1.0" encoding="UTF-8"?>` — well-formed at a glance; `<loc>` count (1748) exactly equals `<url>` count (1748), no unclosed/mismatched tags detected by tag-count parity.

**PASS** — valid XML, single well-formed urlset, correctly declared in robots.txt.

## 2. Size / URL-count limits (Google cap: ≤50,000 URLs AND ≤50 MB uncompressed)

- Total `<loc>` entries: **1,748** (`grep -o "<loc>" sitemap.xml | wc -l`).
- File size: **345 KB**.
- Both **well under** the 50,000-URL / 50 MB ceiling (3.5% of the URL cap, 0.7% of the size cap). No split-with-index is needed at current scale.

**PASS.**

## 3. Coverage Breakdown (measured via path-prefix `awk` split, reconciles exactly to 1748)

| Path prefix | Count | Notes |
|---|---|---|
| `/blog/*` (articles) | **1,582** | via `grep -c "/blog/" locs.txt` (anchored to the `/blog/slug` pattern, excludes the `/blog` listing page itself) |
| `/blog` (listing page) | 1 | counted separately from articles above |
| `/store/*` | **53** | store profile pages |
| `/c/*` | **61** | per-code/coupon landing pages (slugs like `كود-خصم-vperfumes-2026`, `منص`, `زد` — these are code-landing pages, not category pages, despite the short path) |
| `/category/*` | **38** | true taxonomy pages (`جمال وعناية شخصية`, `تطبيقات`, `مواقع عالمية`, etc.) — confirmed via anchored regex `^https://www.dealpulseksa.com/category/`; the earlier unanchored substring grep on `/category/` returned 59, which was a false positive (matching `/category/` as a substring inside 21 other-type URLs, not real category pages) |
| Static/utility pages | 13 | `/`, `/stores`, `/categories`, `/trending`, `/deals`, `/calendar`, `/national-day`, `/back-to-school`, `/faq`, `/how-it-works`, `/about`, `/privacy`, `/terms` |
| **Total** | **1,748** | 1,582+1+53+61+38+13 = 1,748, matches direct `<loc>` count exactly |

### Coverage vs. expected scale
- Memory (`blog_massive_content_session.md`) recorded **1,564 blog articles counted live 2026-08-08** via `grep -cE "^\s*slug:" lib/blog.ts`. Sitemap shows **1,582** `/blog/*` article URLs two days later (2026-08-10) — a **+18 delta over 2 days**, consistent with the ongoing high-volume publishing cadence documented in that same memory file. **No shortfall, no silent truncation** relative to the known blog corpus.
- Memory (`db_foundation_audit.md`) recorded **`master` = 52 rows, counted live 2026-08-05**. Sitemap shows **53** `/store/*` pages five days later — proportionate (one net addition), not a gap.
- **No evidence of the documented past incident** (a 500 on one locale route silently emptying the sitemap): total count (1,748) is in the expected range for ~1,582 blog + ~53 stores + ~61 codes + ~38 categories + 13 utility pages, and the file did not truncate at any suspicious round number (e.g., not stopping at exactly 1000 or 500).

## 4. Locale / Canonicalization Checks

- `/en/` or `/en` entries: **0** (`grep -c "/en/"` and `grep -c "/en$"` both 0). Correct — this site is Arabic-only, no `/en` route, so absence here is correct behavior, not a gap.
- Non-`https` (`http://`) entries: **0**.
- Apex-domain (`dealpulseksa.com` without `www`) entries: **0** — every `<loc>` uses the canonical `www` host. Correct given the apex 308-redirects to `www`.
- Misspelled-domain (`dealpulesksa`) entries: **0**.
- Duplicate `<loc>` values: **0** (`sort | uniq -d` empty).

**PASS on all four locale/canonicalization checks.**

## 5. Deprecated Tags (priority / changefreq)

- `<priority>` present on **1,748 / 1,748** URLs (100%).
- `<changefreq>` present on **1,748 / 1,748** URLs (100%).
- Both tags are **ignored by Google** (per Search Central docs) and add no ranking value — pure dead weight in every one of the 1,748 entries. **Info-level finding**: safe to strip in a future sitemap-generator revision to shrink the file, not urgent given size is far under caps.

## 6. `lastmod` Accuracy

- `<lastmod>` present on **1,739 / 1,748** URLs; **9 URLs have no `<lastmod>` at all** — these are exactly 9 of the 13 static/utility pages (`/blog`, `/calendar`, `/national-day`, `/back-to-school`, `/faq`, `/how-it-works`, `/about`, `/privacy`, `/terms` — confirmed by direct inspection of the raw XML for those entries). Missing `<lastmod>` on evergreen static pages is a minor/Low finding, not a validity failure (the tag is optional per the sitemap protocol).
- Format check: sampled values are valid W3C datetime, e.g. `2026-04-20T00:00:00.000Z`, `2026-08-10T14:25:06.451Z` — ISO-8601 with `Z` UTC suffix, valid.
- **Distribution (not all-identical, so this passes the "real dates" check)**: `sort | uniq -c | sort -rn` on all `<lastmod>` values shows **80 distinct timestamps** across 1,739 dated URLs, but **heavily clustered**:
  - 387 URLs share `2026-07-11T00:00:00.000Z`
  - 310 URLs share `2026-07-04T00:00:00.000Z`
  - 222 URLs share `2026-07-10T00:00:00.000Z`
  - 117 URLs share `2026-08-10T14:25:06.451Z` (today, millisecond-precision — these are the dynamic pages: home, /stores, /categories, /trending, /deals, plus some store/category pages, all stamped with build/request time rather than actual content-change time)
  - 101 URLs share `2026-06-26T00:00:00.000Z`
  - **Finding (Low/Medium)**: the three biggest clusters (387+310+222 = 919 URLs, ~53% of all dated URLs) look like **bulk-publish-date stamps** (all articles published in one batch got one shared date), not per-article "last significant change" dates as Google's guidance asks for. This isn't fabrication (dates aren't literally identical across the whole file, so it clears the crudest "all identical" red flag), but it doesn't reflect genuine per-page edit history either — it's a proxy for "publish batch," not "last significant change." Recommendation: if the sitemap generator can pull a real per-article `updatedAt` from the blog data source, do so; if it currently just stamps "date added to lib/blog.ts," that's an approximation worth flagging to the owner, not a hard failure.
  - The 117 URLs stamped with `2026-08-10T14:25:06.451Z` (this run's fetch timestamp, millisecond precision) are almost certainly stamped with **current request/build time**, not actual content-modification time — this is the classic "lastmod = today, every time" anti-pattern Google explicitly discounts as a trust signal. Applies to the site's most important pages (home, /stores, /categories, /trending, /deals + a chunk of dynamic store/category pages).

## 7. URL Status Spot-Check (5 sampled, per brief's cap)

| URL | Status |
|---|---|
| `https://www.dealpulseksa.com/` | **200** |
| `https://www.dealpulseksa.com/blog/alibaba-camping-outdoor-gear-wholesale-saudi-arabia` | **200** |
| `https://www.dealpulseksa.com/store/جي كارد` (store sample #3) | **200** |
| `https://www.dealpulseksa.com/c/منص` (code-page sample #2) | **200** |
| `https://www.dealpulseksa.com/category/مواقع عالمية` (category sample #2) | **200** |

All 5 sampled URLs (one from each of the 5 URL-type buckets: static, blog, store, code, category) returned **200** with `curl -s -o /dev/null -w "%{http_code}" -L`. No redirects (308/301/302) or errors observed in this sample. **This is a 5-URL spot-check, not a full crawl** — it does not rule out non-200s elsewhere in the other 1,743 URLs; a full status audit would need a separate crawl pass outside this budget.

## 8. `/c/` vs `/category/` — Naming Collision Risk (flagged, not fully diagnosed here)

Two structurally different systems both live under short, easily-confused path segments:
- `/c/<slug>` (61 URLs) = **per-coupon-code landing pages** (e.g., `/c/كود-خصم-vperfumes-2026`)
- `/category/<slug>` (38 URLs) = **true category/taxonomy pages** (e.g., `/category/تطبيقات`)

These are different content types serving different intents, and the 5-URL spot-check sample shows both resolve 200 independently — no evidence of them being duplicate/competing pages for the same query. This is a distinct system from the already-documented `/c/` ↔ `/store` title cannibalization issue in memory (`seo_c_store_cannibalization.md`); flagging the `/c/` vs `/category/` path-naming overlap here only as a readability/maintenance note for whoever reads server logs or GSC path filters — `/c/` and `/category/` are easy to conflate at a glance. Not re-diagnosing the known `/c/`↔`/store` cannibalization issue here since it is already tracked elsewhere.

## 9. Quality Gates — Location Pages

Not applicable: this sitemap has **zero** programmatic city/location pages (`/store/*` are individual merchant profile pages, not `city × store` combinations; `/category/*` and `/c/*` are likewise not geo-doorway pages). The 30+/50+ location-page thresholds in this skill's quality-gate policy do not trigger — **no warning, no hard stop**.

## Summary — Pass/Fail Table

| Check | Result | Evidence |
|---|---|---|
| Valid XML | PASS | tag-count parity, well-formed urlset |
| Sitemap index vs flat | Flat (single file) | 0 `<sitemapindex>`/`<sitemap>` tags |
| ≤50,000 URLs | PASS | 1,748 measured |
| ≤50 MB | PASS | 345 KB measured |
| robots.txt declares sitemap | PASS | direct curl of robots.txt |
| No `/en` entries | PASS | 0 matches, correct per Arabic-only policy |
| Canonical `www` host only | PASS | 0 apex, 0 http, 0 misspelled-domain entries |
| No duplicate `<loc>` | PASS | 0 dupes |
| 5-URL status spot-check | PASS (200 all 5) | curl -w "%{http_code}" -L, not exhaustive |
| priority/changefreq present | Info — remove (ignored by Google) | 1,748/1,748 have both tags |
| lastmod coverage | 1,739/1,748 (9 static pages missing) | Low severity |
| lastmod authenticity | Medium — 53% clustered in 3 bulk-publish dates; ~117 stamped with current-fetch-time | flag for real per-article `updatedAt` |
| Silent-truncation incident check | PASS — no shortfall vs. known corpus (1,582 sitemap vs 1,564 memory-counted 2 days prior; 53 store pages vs 52 master rows 5 days prior) | cross-referenced against `blog_massive_content_session.md` and `db_foundation_audit.md` |
| Location-page quality gates | N/A | no city/location doorway pages present |

## What Was NOT Done (explicitly, per turn budget)
- Did not read `sitemap.ts` / any Next.js source (per brief's instruction).
- Did not crawl the site independently to build a "missing pages" diff (crawled-page inventory vs. sitemap coverage) — that requires a separate crawl pass, out of scope for this budget.
- Did not check all 1,748 URLs for status codes — only 5 sampled, per brief's cap.
- Did not verify noindex/redirect status on any URL beyond the 5-URL HTTP-status spot-check.
