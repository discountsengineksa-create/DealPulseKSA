---
name: web-blog-monolith-oom-and-client-prop-serialization
description: "next dev OOMs on the 5.8MB lib/blog.ts monolith; client-component props serialize into page HTML — trim to card fields to stay under Googlebot's 2MB crawl limit"
metadata: 
  node_type: memory
  type: project
  originSessionId: 1de45ec2-9d7b-4584-bbb4-3afff35c7be3
---

2026-07-11: Ahrefs site audit flagged **"Page size > 2MB"** (1 page) + **1,450 "page has links to redirect"**. Root causes + fixes (web `6a70e1f`):

1. **Sitewide Footer Discord link** used `discord.gg/9U6cn2Kn` which 301-redirects → changed to `discord.com/invite/9U6cn2Kn` (final URL). It's in `components/Footer.tsx` so it appeared on *every* page → one edit cleared the ~1,450 redirect notices.

2. **`app/blog/[slug]/page.tsx`** passed the full `related` `BlogPost[]` (6 posts **with** `body`) into the `BlogPostContent` **client component**. Next.js serializes every prop of a client component into the page HTML → 6 complete article bodies embedded in every article page → the heaviest tipped past 2MB. Fixed by `.map()`-ing `related` to card fields only (slug/title/excerpt/category/readTime/date), mirroring the identical `/blog` fix (which had gone 2.75MB → OK). **Lesson: anything passed to a `'use client'` component is serialized into the HTML — never pass full post bodies; trim to display fields.**

3. **⚠️ Ceiling hit:** `next dev` **OOMs** ("Fatal process out of memory: Zone" / "AlignedAlloc Allocation failed") when compiling blog routes, **even with `NODE_OPTIONS=--max-old-space-size=8192`**, because `lib/blog.ts` is **5.8MB / 1339 posts**. It compiles `/` fine but dies on `/blog/[slug]`. **Cannot render or measure blog pages locally — verify blog changes via the Vercel build + Ahrefs re-crawl, not local dev.** The monolith is a growing liability (future: split per-cluster, or move bodies to MDX/DB so they're not all in one JS module).

**RESOLVED 2026-07-11 (web `6211710`):** `/blog` was still 3.64MB (renders all ~1,340 cards) — the related-trim fix only touched article pages, not the index. Fixed by restructuring `/blog` into a **category hub → /blog/category/[slug] → article** network (no articles deleted, no pagination). `lib/blog.ts` now has: `CATEGORY_ALIASES` (folds ~60 messy Arabic `category` values → 20 canonical), `getBlogCategories()`, `getBlogCategory()`, `getPostsByCategory()`, and **`toCard()`** (strips a post to card fields — use it for ANY client list to stay under 2MB). `/blog` = hub component `BlogHub.tsx` (category cards + 12 latest). Largest category ≈ 178 cards ≈ ~400KB. `BlogList` gained optional `heading`/`lead` props (reused by category pages). Sitemap includes the category URLs.

Ahrefs triage note: only 🔴 Errors matter — "Page size >2MB" and "links to broken page". The scary-looking counts ("1,450 redirect", "Pages to submit to IndexNow") are 🔵 Notices. See [[seo-deep-audit-fixes]] [[blog-internal-link-deorphan]] [[content-programmatic-strategy]].
