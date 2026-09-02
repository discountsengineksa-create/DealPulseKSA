---
name: Maqalat i18n Architecture (next-intl v4)
description: Bilingual (AR+EN) full parity setup for maqalat.org — decisions, file layout, and traps learned the hard way.
type: reference
originSessionId: 14a723a5-c3b8-4b2e-9b1e-b55d65dd193f
---
Full AR/EN parity applied 2026-09-01. Initial scaffolding 2026-08-31.

## URL structure
- `defaultLocale: 'ar'` + `localePrefix: 'as-needed'`
- Arabic stays at `/` (preserves indexed URLs — no SEO reset)
- English at `/en/*`
- Middleware has `localeDetection: false` — no browser-based redirect; user switches via `<LanguageSwitcher>`

## File layout
```
i18n/
  config.ts      — locales, defaultLocale, rtlLocales, isRtl helper
  routing.ts     — defineRouting({ locales, defaultLocale, localePrefix: 'as-needed' })
  navigation.ts  — createNavigation → Link, redirect, useRouter, usePathname
  request.ts     — getRequestConfig with dynamic message import
messages/
  ar.json        — site, nav, footer, language, common
  en.json        — same shape
middleware.ts    — createMiddleware wrap + matcher excluding _next/api/system assets
app/
  layout.tsx     — root: <html lang={fromHeader}> + Analytics + GoogleAnalytics + GoogleAdSense
  [locale]/
    layout.tsx   — NextIntlClientProvider + Header + Footer + JsonLd + generateMetadata(hreflang alternates)
    page.tsx, about/, contact/, privacy/, terms/, editorial-policy/, tools/, [slug]/, c/[cluster]/, not-found.tsx
  sitemap.ts     — root: emits AR+EN URLs w/ hreflang alternates
  icon.tsx, apple-icon.tsx, og-default.png/  — locale-agnostic
```

## Root layout reads locale from middleware header
`app/layout.tsx` cannot receive params (no [locale] segment), so:
```tsx
const headersList = await headers();
const locale = headersList.get('x-next-intl-locale') || defaultLocale;
```
Fallback to `defaultLocale` covers sitemap.xml, robots.txt, ads.txt — paths middleware excludes.

## Pragmatic shortcuts taken (progressive migration)
- **Only Header + Footer use `useTranslations()`** for MVP. Body content of individual pages still contains hardcoded Arabic strings — safe because those pages only render for AR locale until EN articles are added.
- **Articles are AR-only until Phase 2.** `app/[locale]/[slug]/page.tsx` explicitly `notFound()` when `locale !== "ar"`. This prevents duplicate content on `/en/{slug}` while the AR canonical exists.
- **`generateStaticParams` for [slug] returns only `{ locale: 'ar', slug }`** — no EN combinations generated. Cluster pages generate both locales (they render UI-driven content that translates via useTranslations even when article body doesn't).

## Adding an English article later
1. Create the EN MDX file (naming convention TBD — pick `.en.mdx` sibling or `content/articles/en/*.mdx`).
2. Update `lib/blog.ts` `getArticle(slug, locale)` to resolve locale-appropriate file.
3. Update `[slug]/page.tsx` to remove the `locale !== "ar"` guard once EN content exists per slug.
4. Update `generateStaticParams` to include EN slugs where files exist.
5. Update sitemap to emit `/en/{slug}` for EN articles with hreflang alternates.

## Verify after any i18n change
```bash
# AR root, EN root
curl -sI https://maqalat.org/ | head -1
curl -sI https://maqalat.org/en | head -1

# hreflang tags (Note: Next.js emits `hrefLang` camelCase, not `hreflang`)
curl -s https://maqalat.org/ | grep -oE '<link rel="alternate"[^>]*>'

# Sitemap alternates
curl -s https://maqalat.org/sitemap.xml | grep -oE 'hreflang="[a-z-]+"' | sort -u

# Existing indexed AR URL preserved
curl -sI https://maqalat.org/zakat-calculator-guide

# EN article should 404 (no EN content yet)
curl -sI https://maqalat.org/en/zakat-calculator-guide  # expect 404
```

## Article system (bilingual via sibling files, applied 2026-09-01)
File-naming convention:
- `content/articles/{slug}.mdx` → Arabic (canonical)
- `content/articles/{slug}.en.mdx` → English sibling (optional per article)

`lib/blog.ts` API:
- `getArticle(slug, locale?)` — reads the matching file, returns null if missing
- `getAllArticles(locale?)` — filters by locale (AR ignores `.en.mdx`, EN only reads `.en.mdx`)
- `hasArabicVersion(slug)` / `hasEnglishVersion(slug)` — filesystem existence checks
- `getAllSlugs()` — union of all slugs across both languages (for sitemap/params)
- `getSearchIndex(locale?)` — locale-scoped index (Header must pass `useLocale()`)
- `getRelatedArticles(article)` — never crosses locale boundary

`app/[locale]/[slug]/page.tsx`:
- `generateStaticParams` emits only `(locale, slug)` pairs where the file exists — no ghost pages
- `generateMetadata` builds hreflang alternates from actual language availability
- No `notFound()` guard for EN — the page just uses `getArticle(slug, "en")` which returns null → 404 naturally

## Watch-outs learned
- **Middleware matcher must exclude `og-default`, `sitemap.xml`, `robots.txt`, `ads.txt`, `fonts`.** Otherwise middleware rewrites break these system routes.
- **Grep pattern for hreflang tags: use `hrefLang`** (camelCase) — Next.js renders JSX attribute as-is.
- **`ENABLED_CLUSTERS` already had `titleEn`** in `lib/clusters.ts` — no cluster metadata change needed.
- **Pages using `<Link>` from `next/link`** still work but don't auto-prefix locale in href. Progressive replace with `@/i18n/navigation` Link as content grows.

## Additional traps found in 2026-09-01 full-parity pass
- **`useTranslations` / `useLocale` in async server components → HTTP 500.** Split into async wrapper (calls `setRequestLocale` + returns `<Body />`) + sync `Body` function that uses the hooks. Same trap on Home page cost one deploy cycle. `About`/`Contact`/`Tools` already used this pattern; `HomePage` didn't.
- **Rich text in translations:** use `t.rich("key", { b: (chunks) => <strong>{chunks}</strong>, link: (chunks) => <Link href="/...">{chunks}</Link> })`. Store as `"<b>bold</b>"` / `"<link>text</link>"` in messages.
- **Long legal pages (privacy/terms/editorial):** don't force them through `messages/*.json`. Use `if (locale === "en") return <EnglishJSX /> else return <ArabicJSX />` in the same file — cleaner for HTML-heavy content that rarely changes.
- **`not-found.tsx` sits inside `[locale]/`** and can use `useTranslations` (marked `"use client"`). Otherwise it'll show its hardcoded strings even on `/en/*` requests via React Server Components streaming.
- **SearchBar / Header components:** the search index prop must be built with `getSearchIndex(useLocale())` in Header, otherwise AR article titles bleed onto EN pages.
- **CWD drift in long sessions.** Bash tool preserves cwd across calls, but sub-operations can silently switch. When committing to maqalat, always verify with `pwd` before `git add/commit/push` — a wrong-directory commit went to the DealPulse repo unnoticed until fetch showed 246 unrelated commits ahead. Anchor with explicit `cd /c/Users/user/Desktop/maqalat && ...` for git operations.
