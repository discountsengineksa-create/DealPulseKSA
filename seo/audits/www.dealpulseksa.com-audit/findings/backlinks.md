# Backlink Profile — dealpulseksa.com (canonical: www.dealpulseksa.com)

**Audit date:** 2026-08-10
**Credential tier verified live:** Tier 0 — Basic (Common Crawl + Verification crawler only). Moz: no key. Bing Webmaster: no key. DataForSEO: not installed.
Command used: `runtime.py run backlinks_auth.py --check --json` → `"tier": 0`, `moz.available: false`, `bing.available: false`.

**Headline finding:** at this credential tier, there is effectively **no usable third-party referring-domain data**. Common Crawl has not crawled this domain at all (confirmed live, both host forms). The only two backlinks this audit could verify by name — the SaaSHub listings — were checked live with the verification crawler and **neither currently contains a link to dealpulseksa.com**. Any number below is a documented **floor**, not a total. Do not read this report as "the backlink profile is weak" — read it as "the backlink profile is **unmeasured**, and the one link source we could check by hand isn't live yet."

---

## Forward Plan — White-Hat Link Sources (put first per brief; this is the actionable half of the report)

All items respect the site's hard constraints: no link buying, no PBNs, no reciprocal-link schemes, no comment/forum spam, no Reddit/Quora seeding (owner-rejected, see `Claude_Memory/seo_owned_channels_pivot.md`). Gate rule already in force (`Claude_Memory/seo_white_hat_only.md`): **any directory that requires a reciprocal link from us, or sells do-follow placement, is refused on sight** — that filter has already killed one live offer (SellWithBoost) and should be applied to every item below before outreach.

### 1. Saudi/regional business & startup directories (citation layer — low DA lift each, but cumulative + free)
- **SaaSHub `saashub.com/deal-pulse-ksa`** — already claimed and verified-by-meta-tag (owner-side). Status is `Not approved`; per live check today, **zero live links** on either the product page or the `/startups/saudi-arabia` regional list (see Verification section below). Action: use the **Feedback/Contact** button on SaaSHub to request approval review — that is the only lever left, no more profile fields to fill.
- **MAGNiTT** (`magnitt.com`) — the MENA startup/company database used by regional investors and press; free company profile listing, legitimate for a Saudi consumer-tech company, dofollow on many listing types. Worth a submission given DealPulse is a real operating Telegram+web product.
- **Monsha'at-affiliated / Saudi SME ecosystem directories** (the same category as the already-completed Find Saudi listing under "اتصالات وإنترنت › تسوّق، تجارة إلكترونية") — repeat the same low-effort profile submission pattern for any additional Saudi business directory in that category (Saudi Bizness, KSA Directory — both already flagged as targets in `Claude_Memory/seo_authority_building.md`, not yet executed per that file).
- **Product Hunt** — free launch listing for the Telegram bot + web app angle ("deal alert bot for Saudi shoppers"). Legitimate, no reciprocal requirement, dofollow profile link, and gives a one-time traffic/PR spike distinct from directory citation value.
- **partner.visitsaudi.com** (Saudi Tourism Authority partner directory) — already identified as a target in `seo_authority_building.md`, not yet executed. Relevant because /calendar covers national occasions; frame the pitch around tourism-adjacent seasonal shopping (National Day, Founding Day) rather than generic "deals site."

### 2. Merchant-side partnership backlinks (highest relevance, because these merchants are *already* paying DealPulse via affiliate commission — the ask is a natural extension of an existing commercial relationship, not cold outreach)
- **Bedinroom** — flagged as priority #1 in `seo_authority_building.md`: DealPulse already built a dedicated content hub (`blog_bedinroom_cluster.md`, 12-19 articles). The natural ask: a "featured partner / where to find our codes" link from Bedinroom's own promotions or partner page. Partner email drafted but reportedly not yet sent — confirm and send.
- **Salla** (`salla_affiliate_channel.md`) — Salla runs an official affiliate/partner programme with DealPulse enrolled (discount + commission, no gate). Salla's own affiliate/partner-showcase pages (if they publish a "our affiliates" or case-study page) are a legitimate ask given 13 attributed orders (~525 SAR) already proven — a real conversion story is exactly what affiliate networks like featuring.
- **Boostiny** — publisher application accepted 2026-08-06 (#52131), second review pending before final agreement. Once the agreement is signed, ask whether Boostiny features approved publishers (many CPA networks run a "meet our publishers" or case-study blog) — a natural next-step ask, not cold.
- **Zid** ("سفير زد" ambassador programme, `zid_affiliate_channel.md`) — ambassador programmes commonly link back to active ambassadors from a directory or blog post; worth asking the Zid partnerships contact directly since DealPulse is already an enrolled ambassador.
- **CodeMap** (`codemap_affiliate_channel.md`) — coupon-only channel with large brands; if CodeMap publishes a publisher/affiliate showcase, same ask applies.
- Do **not** pursue DCM Network for this purpose — memory flags it as a low-value channel with an account that was previously locked for code scarcity, not a link asset.

### 3. Digital-PR hooks built around the `/calendar` seasonal asset
`/calendar` is a real, live, auto-rotating asset (Saudi occasions ranked by proximity, already the site's strongest internal-linking hub as of 2026-08-08 per `domain_authority_plan.md`). It is exactly the kind of "linkable asset" that earns citations without payment, because it answers a recurring seasonal question rather than promoting a single merchant:
- **National Day / Founding Day (Sept)**: pitch Saudi retail/marketing/business-news outlets that cover White Friday/national-holiday retail trends annually with an **original data angle** DealPulse can actually source live — e.g., "N stores currently running Founding Day discounts, sourced from our own live coupon database" — a data-journalism hook, not a guest post ask. This only works if the underlying number is counted live from `master` at pitch time, not asserted from memory.
- **Ramadan**: same data-hook pattern — "live count of merchants running Ramadan promotions" — pitched to Gulf lifestyle/consumer outlets during the pre-Ramadan news cycle.
- **Back-to-school (Aug-Sept)**: the natural angle is parenting/family content, not press — this is the same audience Bedinroom/Mamas & Papas clusters already target (`blog_mamaspapas_cluster.md`), so the parenting-blog outreach and the merchant-partnership outreach in section 2 can be combined into one pitch: "auto-updating back-to-school savings calendar for Saudi parents."
- **White Friday (Nov)**: highest-volume seasonal news cycle in KSA retail; same original-data pitch as National Day, timed for the week White Friday coverage starts running.
- In every case, the pitch offers a **citation of live, verifiable data**, not a paid or reciprocal placement — this keeps every one of these inside the white-hat gate.

### 4. Foundational citations already in progress (finish these before starting anything new)
Per `seo_authority_building.md`, this layer was already scoped and partially executed — closing it out is lower effort than any new item above:
- Trustpilot — reported complete ("أول باكلينك مكتمل").
- Find Saudi — listed 2026-07-14, low authority value but done.
- Google Business Profile, LinkedIn company page, Crunchbase — reported as planned, not confirmed complete in the files opened for this audit; verify status before adding to a "done" list.

---

## What Was Actually Measured Today

### Common Crawl domain graph (Tier 0, confidence: 0.50, quarterly release `cc-main-2026-jan-feb-mar`)
| Host checked | In crawl | In rankings | PageRank | Harmonic centrality |
|---|---|---|---|---|
| `dealpulseksa.com` | No | No | null | null |
| `www.dealpulseksa.com` | No | No | null | null |

Command: `runtime.py run commoncrawl_graph.py <domain> --json`. Response note: *"Domain not found in Common Crawl data. It may be too new, too small, or not yet crawled."* This is a genuine measurement (both host forms returned identical `null` results, not a script error) — Common Crawl simply has no page from this domain in its graph as of this release. Source: https://commoncrawl.org/web-graphs

### Backlink verification crawler (Tier 0, confidence: 0.95 for what it directly observed)
Two known/claimed backlink sources were checked live against both host forms (`https://www.dealpulseksa.com` and `https://dealpulseksa.com`, to rule out a www/apex mismatch):

| Source page | HTTP status | Link to dealpulseksa.com found? | Status |
|---|---|---|---|
| `https://www.saashub.com/deal-pulse-ksa` | 200 | No | `link_removed` |
| `https://www.saashub.com/startups/saudi-arabia` | 200 | No | `link_removed` |

Command: `runtime.py run verify_backlinks.py --target <host> --links known_links.json --json`, run twice (www and apex targets), identical result both times.

**This contradicts a prior memory note** (`Claude_Memory/saashub_directory_listing.md`) claiming the `/startups/saudi-arabia` page links out dofollow via `rel=""` on the hero link, based on a manual `curl` check against a different slug context (`almowafir`/`notah.ai` examples were the ones actually spot-checked in that memory entry — DealPulse's own inclusion on that specific listing was not directly curl-verified there). Live crawler check today shows **no link to DealPulse's domain on either SaaSHub page right now**. Trust today's live result over the memory note. Two plausible explanations, neither confirmed: (a) the SaaSHub product page's `Not approved` state (documented in the same memory file) may also suppress the startups-directory link, or (b) the crawler fetched static HTML and the actual link is injected client-side on that specific listing page — the crawler's own classifier reported `link_removed` (parsed HTML, no match) rather than `unverifiable_js` (SPA-shell detected), which argues against explanation (b) but does not rule it out with certainty. Recommend a manual browser check as a tiebreaker before writing this off as "listing lost."

No other named backlink sources (Trustpilot, Find Saudi, Google Business Profile, etc.) were supplied as URLs for this audit run, so they were not verified here — their "complete" status in memory is unconfirmed by live crawl in this report.

---

## Backlink Health Score

**INSUFFICIENT DATA — no numeric score produced.**

Per the scoring framework, a numeric Backlink Health Score requires data across the 7 weighted factors (referring domains, domain quality distribution, anchor naturalness, toxic-link ratio, link velocity, follow/nofollow ratio, geographic relevance). At Tier 0 with Common Crawl returning zero rows for this domain:

| Factor | Weight | Data available? |
|---|---|---|
| Referring domain count | 20% | No — CC doesn't provide this directly; no Moz/DataForSEO |
| Domain quality distribution | 20% | No |
| Anchor text naturalness | 15% | No |
| Toxic link ratio | 20% | No |
| Link velocity trend | 10% | No (DataForSEO-only factor) |
| Follow/nofollow ratio | 5% | Partial — only for the 2 manually-checked SaaSHub URLs (both currently: no link at all, so N/A) |
| Geographic relevance | 10% | No |

**0 of 7 factors have real coverage** (well under the 4-factor floor for producing a number). Producing a score here would be fabrication dressed as measurement — explicitly against the standing "no numeric score on insufficient data" rule and the project's zero-fabrication wall.

---

## Priority Recommendations

| Priority | Action | Why |
|---|---|---|
| Critical | Get real backlink visibility: sign up for Moz free tier (2,500 rows/month, https://moz.com/products/api) or a Bing Webmaster key (free, requires site verification) — either moves this from Tier 0 to Tier 1/2 and turns "insufficient data" into an actual score | Everything above this line is structurally invisible until a real API is connected; Common Crawl alone cannot see a domain this small/young |
| High | Manually browser-check `saashub.com/startups/saudi-arabia` for DealPulse's actual link status (resolve the memory-vs-live discrepancy above), then follow up via SaaSHub's Feedback/Contact button requesting approval review on the main listing | Cheapest, already-invested link source; currently returning zero live value despite completed verification |
| High | Send the already-drafted Bedinroom partner-link outreach email | Highest-relevance link available (active affiliate + dedicated content hub already built); pure execution gap, not a research gap |
| Medium | Submit MAGNiTT company profile + Product Hunt launch listing | Free, no reciprocal requirement, legitimate regional relevance, not yet attempted |
| Medium | Ask Salla / Boostiny (post-agreement) / Zid whether they run a publisher/ambassador showcase page | Natural extension of an existing paid commercial relationship — near-zero cold-outreach cost |
| Low | Time National Day / Ramadan / White Friday data-driven PR pitches to the actual news cycle (Aug-Sept and pre-Ramadan windows) using live-counted merchant numbers from `/calendar` at pitch time | Legitimate digital-PR angle already supported by a live, real asset; low cost but needs lead time and a real count at the moment of pitching, not a stored figure |

## Data Source Summary

| Source | Coverage | Confidence | Freshness |
|---|---|---|---|
| Common Crawl Web Graph | Domain-level presence/PageRank/harmonic centrality | 0.50 | Quarterly release `cc-main-2026-jan-feb-mar`, cached |
| Verification crawler | 2 manually-supplied URLs only | 0.95 (direct HTTP fetch + HTML parse, not an inference) | Live, checked today (2026-08-10) |
| Moz / Bing / DataForSEO | Not available this tier | — | — |
| Memory files (`saashub_directory_listing.md`, `seo_authority_building.md`, `domain_authority_plan.md`) | Historical context, partly superseded by today's live check | Not independently re-verified except where noted above | Various dates, see inline citations |

**Not duplicated here:** on-page/technical SEO (already verified clean per audit brief: valid 1748-URL sitemap, security headers, SSR, 0.95 mobile PageSpeed) and E-E-A-T/content quality — see `/seo content <url>` and `/seo technical <url>` for those tracks.
