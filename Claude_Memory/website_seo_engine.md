---
name: dealpulseksa.com SEO Engine
description: Architecture and conventions of the SEO/structured-data layer added to the website on 2026-05-10
type: project
originSessionId: 97c9af5f-c80f-4760-8949-7ffa1e4c9f16
---
The website at `c:\Users\user\Desktop\dealpulseksa-web\` has a structured SEO layer with single-source-of-truth conventions.

**Why:** User asked for a comprehensive SEO engine ("ultimate SEO & technical engine") on 2026-05-10. To prevent drift, all SEO-relevant config flows through two modules and downstream files import from them — never duplicate.

**How to apply:**
- **Single source of truth files** — never inline SEO constants:
  - [`lib/seo/constants.ts`](c:\Users\user\Desktop\dealpulseksa-web\lib\seo\constants.ts) — `SITE_URL`, `SITE_NAME_*`, `LOGO_URL`, `STATIC_PAGES` (drives sitemap), `PRIVATE_PAGES` (drives robots), locale tags, `BILINGUAL_ENABLED` toggle.
  - [`lib/seo/schema.ts`](c:\Users\user\Desktop\dealpulseksa-web\lib\seo\schema.ts) — `siteGraph()` builds the @graph (Organization + WebSite + LocalBusiness + SoftwareApplication) emitted ONCE in `app/layout.tsx`. Per-page builders: `storeProductSchema`, `breadcrumbList`, `itemListSchema`, `collectionPageSchema`, `faqPageSchema`, `howToSchema`, `blogPostingSchema`. Use `jsonLd(node)` to render to a string for `dangerouslySetInnerHTML`.
- **`BILINGUAL_ENABLED = false`** — flip to `true` once `app/[locale]/` route tree exists. Sitemap and `metadata.alternates.languages` automatically switch to bilingual hreflang clusters. Until flipped, hreflang stays self-referential to avoid Google seeing 404s.
- **New content pages** (Arabic-only currently): `/faq`, `/deals`, `/how-it-works` — wired into Header nav and Footer, included in sitemap via STATIC_PAGES.
- **Dynamic OG images** at [`app/og/store/[slug]/route.tsx`](c:\Users\user\Desktop\dealpulseksa-web\app\og\store\[slug]\route.tsx) — Edge runtime, used by store/[slug] generateMetadata. To regen, just bump the slug; cache invalidates with ISR.
- **On-demand revalidation hook**: `POST /api/revalidate` with `{ secret, paths[] }` and `POST /api/indexnow` with `{ secret, urls[] }` — both gated by `REVALIDATE_SECRET` env. The FastAPI backend should call both whenever a coupon row in `master` changes.
- **Required env vars** (Vercel): `REVALIDATE_SECRET`, `INDEXNOW_KEY` (also place text file at `public/{INDEXNOW_KEY}.txt`), `NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION`, `NEXT_PUBLIC_BING_SITE_VERIFICATION`.
- **Security headers** centralized in [`next.config.mjs`](c:\Users\user\Desktop\dealpulseksa-web\next.config.mjs) `headers()`: HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, X-Frame-Options. CSP intentionally NOT added (would break inline JSON-LD + framer-motion without nonce wiring).
- **i18n migration deferred**: full `app/[locale]/` restructure with `next-intl` is the next major task. Plan file at `C:\Users\user\.claude\plans\tidy-foraging-whisper.md` covers it. When ready, install `next-intl`, add `middleware.ts` + `i18n/request.ts` + `messages/{ar,en}.json`, move all routes under `[locale]/`, then flip `BILINGUAL_ENABLED` to `true`.
- **AggregateRating** is synthesized from `total_link_clicks + total_coupon_copies` (Bayesian-smoothed, capped at 4.9, only emits when ≥10 interactions). Flagged as B-tier signal — replace with real Reviews table when backend grows one.
