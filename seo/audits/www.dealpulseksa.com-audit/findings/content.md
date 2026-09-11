# Content Quality Findings — dealpulseksa.com Blog

**⚠️ Correction to prior version:** an earlier pass of this file called the blog a
keyword-selection failure with near-zero demand. That was built on truncated
Search Console data and is retracted. Page-level GSC data (28 days, untruncated)
shows the opposite: the blog is the site's single biggest click source.

## The real shape of the data

| Section | Impressions | Clicks | CTR | Pages |
|---|---|---|---|---|
| **/blog** | 3,250 | **50** | 1.54% | 565 indexed of 1,564 published |
| /store | 6,693 | 17 | 0.25% | 49 |
| /calendar | 1,859 | 38 | 2.04% | 1 |
| /category | 815 | 4 | 0.49% | — |
| /c | 411 | 0 | 0.00% | 35 |
| **Site total** | 12,957 | 132 | 1.02% | — |

Blog: 1,564 articles live, 565 ever appeared in search, **40 have earned a
click, 524 have earned zero.** 2.5% of the catalogue produced 100% of the
blog's clicks. This is not a demand problem — CTR on the pages that *do* rank
(1.54%, and the top winners sit at position 5–9) is respectable. It's a
**topic-selection problem inside an otherwise working format.**

## Method

Read source (`lib/blog.ts`, 1,564 articles, confirmed via
`grep -cE "^\s*slug:"`) directly rather than fetching rendered pages — content
is identical, and this let me pull exact word counts by line range instead of
estimating.

**3 winners** (from the top-10-by-clicks list):
- `school-records-guide-saudi` — 5 clicks, pos 5.8, 120 words
- `school-operational-plan-guide-saudi` — 3 clicks, pos 8.8, 103 words
- `aliexpress-carlinkit-5-setup-tutorial-saudi-arabia` — 3 clicks, pos 6.2, 461 words

**3 zero/low-click comparables** — same site, same publish cadence, picked
from the two largest catalogue clusters that are structurally different from
the winners:
- `chanel-perfumes-guide-saudi-arabia` — 927 words (perfume-brand cluster, 79 articles total)
- `perfume-brands-celebrity-saudi-arabia` — 661 words (same cluster)
- `aliexpress-70mai-dash-cam-review-saudi-arabia` — 457 words (same
  aliexpress-car cluster, published the same day, same author, same FAQ/
  troubleshooting/comparison structure as the carlinkit-5 winner)

The third comparable is the load-bearing one: it rules out "just add
structure" as the fix, because it already has the winner's structure and
still (on all available evidence) isn't a winner.

## What the winners have in common

| Signal | `school-records` | `school-operational-plan` | `carlinkit-5-setup` |
|---|---|---|---|
| Title = literal query a person types | "السجلات المدرسية 1447-1448هـ" | "الخطة التشغيلية للمدرسة 1447-1448هـ" | "دليل تركيب Carlinkit 5.0 خطوة بخطوة" |
| Answers a task, not describes a product | defines record types + how to store them | defines plan components + how to build one | numbered install steps + 5 named troubleshooting fixes |
| Recurring/renewing audience | every Hijri school year, every teacher | every school year, every school admin | every buyer of that exact SKU, once, but a steady drip of new buyers |
| Named specifics | document formats (Word/PDF), named related docs | plan components, review cadence | named car brands/models, named failure modes ("يسخن", "يتقطّع الصوت"), named settings paths |
| Word count | 120 | 103 | 461 |

**6 of the top 10 winners by click are AliExpress car-diagnostic-tool /
tutorial articles** (Carlinkit setup, Carlinkit comparison, coolant-pressure
tester, differential-oil transfer, Hyundai/Kia GDS, Toyota Techstream) —
this is not one lucky article, it's a repeatable pattern inside one narrow
niche: Arabic-language install/troubleshooting content for specific
diagnostic hardware essentially doesn't exist elsewhere, so a plain,
correctly-named how-to wins position 4–9 with almost no competition.

## What the zero-click comparables have instead

`chanel-perfumes-guide-saudi-arabia` (927 words) and
`perfume-brands-celebrity-saudi-arabia` (661 words) are both markdown
reformats of the partner store's product catalogue: brand history paragraph →
table of every SKU/concentration/size. No question is being answered — the
title ("عطور شانيل في السعودية") doesn't match a task a person searches for
by name; it competes with every perfume retailer's own category page,
Chanel's own site, and dozens of Arabic beauty blogs. **79 articles in this
one cluster share this exact shape** (`perfume-brands-*` + `*-perfumes-guide-
saudi-arabia`, counted via grep) — a fifth of the whole catalogue's failure
mode is one template applied 79 times.

`aliexpress-70mai-dash-cam-review-saudi-arabia` is the control that isolates
the real variable. It has the **same author, same publish date, same
troubleshooting-table/comparison/FAQ structure, same word count (457 vs. 461)**
as the carlinkit-5 winner — and by every visible signal is not converting
impressions into clicks the way its sibling is. The difference isn't format,
it's **intent class**: "install/fix a niche accessory" is a support query with
near-zero Arabic competition; "review a mass-market dash cam" is a commodity
review query competing against YouTube, AliExpress's own review aggregation,
and every gadget-review site in two languages. Structure is necessary
(confirmed by the winners all having it) but **not sufficient** — the 70mai
article proves a well-built article on the wrong intent class still loses.

## The replicable editorial rule

**Before writing an article, answer two questions. Both must be yes, or don't
write it.**

1. **Is the title the literal string a specific person types into Google when
   they have a task, not a curiosity?** ("طريقة تركيب Carlinkit 5" /
   "السجلات المدرسية" — not "عطور شانيل" or "أفضل عطور 2026"). A catalogue
   description is not a task. A brand-history page is not a task.
2. **Does that task have a narrow, low-competition Arabic search surface** —
   either because it repeats on a calendar (school-year documents, seasonal
   admin paperwork — same query, renewed audience every Hijri year) or
   because it's a specific-SKU support/install pain point that no other
   Arabic publisher has bothered to document (diagnostic tools, install
   tutorials, troubleshooting)? If the topic is a commodity category already
   covered by big review sites or YouTube (dash-cam reviews, "best
   perfumes"), the answer is no even with perfect structure.

If both are yes: write it short. The two winning school articles are 103–120
words — proof word count is not the lever (matches Google's own position that
word count isn't a ranking factor; these pages win on precision, not depth).
If the task is technical/multi-step (install, troubleshoot), structure does
matter — numbered steps, named failure modes, FAQ block — but only as
execution quality on top of a correct topic choice, never as a substitute for
one.

**Screen for "no" before writing:**
- Title names a *brand* or *category* ("عطور X", "أفضل متاجر Y") instead of a
  *task* → catalogue-reformat trap, kills the 79-article perfume cluster and
  will kill any future cluster shaped the same way.
- Title matches a query already dominated by video/major review sites
  (product reviews of mainstream consumer electronics) → 70mai trap: good
  execution, wrong intent class, likely zero-click regardless of quality.
- The topic doesn't recur (no seasonal/annual trigger) and isn't a rare
  support pain point → no repeat audience to sustain rankings.

## Portfolio-level implication (not just this article's ask, but the obvious next question)

278 of 1,564 articles (18%) are already in the AliExpress cluster where 6 of
10 winners live — the untapped opportunity there is auditing which of those
278 are catalogue/review-shaped (70mai-pattern, likely dead) versus
install/troubleshoot-shaped (carlinkit-5-pattern, likely alive) and
redirecting future production toward the latter. The 79-article perfume
cluster and its siblings (brand-guide catalogue reformats across other
categories — this pattern likely recurs beyond perfume; not separately
counted here) are the clearest candidates to **stop producing new entries
for**, not to delete — Google's March 2024 Helpful Content merge evaluates
this at the site level via core updates, so a large body of thin,
templated, zero-click catalogue pages is a plausible drag on how the rest of
the site is trusted, not just isolated dead weight. That's a hypothesis, not
a measured claim — pair it against `seo/audits/.../findings/cluster.md` and
`sitemap.md` before acting on it.

## Content quality score: not applicable as a single number here

This brief is a targeted topic-selection diagnosis, not a full E-E-A-T pass.
The winning articles score well on the signals that matter for this
question — task-specificity, named specifics, correct title-to-intent match —
and score low on traditional "thin content" heuristics (103–120 words), which
is itself the finding: for this site, word-count-based thin-content flags are
the wrong lens. A full E-E-A-T/AI-citation pass across the 1,564-article
catalogue (author bios, freshness signals, structured data per template) was
out of scope for this run and should be a separate pass if needed.

## Files read

- `C:\Users\PC\Desktop\dealpulseksa-web\lib\blog.ts` (1,564 articles,
  confirmed via `grep -cE "^\s*slug:"`) — read directly by line range for:
  `school-records-guide-saudi` (22461–22521), `school-operational-plan-guide-
  saudi` (22857–22908), `aliexpress-carlinkit-5-setup-tutorial-saudi-arabia`
  (36373–36381), `chanel-perfumes-guide-saudi-arabia` (1913–2081),
  `perfume-brands-celebrity-saudi-arabia` (36–196),
  `aliexpress-70mai-dash-cam-review-saudi-arabia` (36363–36371)
