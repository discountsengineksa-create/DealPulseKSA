# Backlink Profile — dealpulseksa.com (canonical: www.dealpulseksa.com)

**Updated: 2026-08-11.** This version supersedes the 2026-08-10 draft — the situation is now measured
four independent ways and they agree, which changes the finding from "unmeasured" to "measured and flat."
This is now the **top SEO priority**: content volume (1,582 blog articles published over the same twelve
months) is proven not to move authority; link count is the only lever left untested.

## Session tooling disclosure (read before trusting anything below)

This delegated session had **no live search tool and no Moz/Ahrefs/Semrush API access**. Its only tools
were file read/write/glob/grep and a shell (`curl` works — outbound HTTP is not blocked). Two consequences:

1. **The headline numbers below (Moz/Ahrefs/Semrush) were supplied by the orchestrating audit agent's
   brief, not independently queried by this session.** `Glob` for `backlinks_auth.py` and `moz_api.py`
   found **zero matches** anywhere in this repository — the claude-seo tier-check tooling described in
   this skill's own instructions is not installed on this machine, so Tier 0-3 commands could not be run
   here. This session's own prior live check (2026-08-10, same audit) independently confirmed the Common
   Crawl piece of the "four ways" claim (`in_crawl: false` for both host forms) — that one data point is
   double-verified. The Moz/Ahrefs/Semrush numbers are trusted as reported but carry **confidence 0.75**
   (secondhand, cross-tool-agreeing, not self-executed) rather than the 1.00/0.85 this skill reserves for
   metrics a session queries itself.
2. **The target list in Deliverable 1 is built from existing domain knowledge, not a live search** — there
   is no WebSearch/WebFetch tool available in this session, so "the search tool is US-based, not
   Saudi-localized" undersells the actual limitation: there was no search step at all. What *is* live is
   the reachability column — every named target below was hit with a direct `curl -sL -A "Mozilla/5.0"`
   request from this session's sandbox (a generic cloud egress point, not Saudi-localized) on 2026-08-11,
   and the HTTP status is reported as observed. A `403` means Cloudflare/bot-protection blocked the raw
   `curl` request, **not** that the site is down — several of those (Product Hunt, AlternativeTo, Gulf
   Business) are well-known live platforms; the `403` is disclosed so it isn't silently upgraded to "verified
   working." A `000` means curl got no response at all in this environment (DNS/network path issue on this
   machine, not a verdict on the target — Trustpilot and goldenpages.com.sa both hit this; flagged as
   **unverified**, not "broken").

---

## What Was Actually Measured (four sources, they agree on the ceiling, disagree on the count)

| Source | Metric | Value | Confidence | Freshness |
|---|---|---|---|---|
| Moz | Domain Authority | **1** | 0.75 (reported, not self-queried) | Checked live per brief, 2026-08-1x |
| Moz | Page Authority (homepage) | **5** | 0.75 | same |
| Moz | Linking root domains | **1** | 0.75 | same |
| Moz | Ranking keywords | **~0** | 0.75 | same |
| Moz | 12-month DA trend | **Flat at 1**, Sep 2025 → Aug 2026 | 0.75 | chart, per brief |
| Ahrefs | Domain Rating | **0** | 0.75 | per brief |
| Ahrefs | Referring domains | **158 total, only 3 followed** | 0.75 | per brief |
| Semrush | Authority Score | **7** | 0.75 | per brief |
| Semrush | Referring domains | **34** | 0.75 | per brief |
| Common Crawl | `in_crawl` | **false**, both `dealpulseksa.com` and `www.dealpulseksa.com` | **0.95** — this session's own live tool run, 2026-08-10, same audit (`commoncrawl_graph.py`) | Quarterly web-graph release, source: https://commoncrawl.org/web-graphs |

**Do not average 1 / 34 / 158 into one number — that would fabricate false precision.** These are three
tools with three independently-crawled, partially-overlapping views of the web, not three measurements of
one fixed true value; disagreement of this size is normal and expected at near-zero authority, not an error
in any one tool. The decision-relevant number is **Ahrefs' followed count: 3** — it is the only figure that
already answers "how many links currently pass authority," which is what the rest of this report is trying
to grow. Moz's "1 linking domain" is almost certainly a strict subset of that same handful (Moz's index is
smaller), and Semrush's 34 is mostly the same nofollow/directory noise Ahrefs counts in its 155 unfollowed.
**Working number for this report: ~3 real dofollow linking domains, against a much larger pile of nofollow
directory noise that isn't moving authority at all.**

Common Crawl's `in_crawl: false` is the sharpest independent confirmation available: Common Crawl's crawler
discovers pages primarily *by following links from pages it already knows about*. A domain with a real,
followed link from any site already in CC's graph would very likely have been picked up by now. Its absence
is consistent with — not merely "not contradicting" — the near-zero linking-domain counts above.

---

## Deliverable 1 — Ranked, Named Target List

Every item respects the standing hard constraints (`Claude_Memory/seo_white_hat_only.md`,
`Claude_Memory/seo_owned_channels_pivot.md`): no link buying, no PBNs, no reciprocal-link schemes, no
comment/forum spam, no guest-post farms, no Reddit/Quora. The gate already established in this project —
**"how is the link paid for? If the answer is a reciprocal link from us, or money for do-follow, refuse on
sight"** — is applied to every row below before it's listed. Reachability = live `curl` result, 2026-08-11.

### Tier A — free, self-serve, or already in motion (do these first)

| Target | Reachable? | Why it accepts this site | Realistic outcome | Effort |
|---|---|---|---|---|
| **SaaSHub — `saashub.com/startups/saudi-arabia`** | Verified 200 (this session's prior live check, 2026-08-10) | Already-claimed listing, "Top 42 Startups based in Saudi Arabia," matched category (eCommerce → Discount Codes). Hero-link `rel` attribute is empty (dofollow) **only after `Approved`** status — currently `Not approved`, zero live link despite completed verification (see `Claude_Memory/saashub_directory_listing.md`). | Entity mention now; **dofollow** once approved. Zero referral traffic expected (English, software-buyer audience, not Saudi shoppers). | Very low — only lever left is the Feedback/Contact button requesting approval review. |
| **Product Hunt — producthunt.com** | curl → 403 (Cloudflare bot-block on raw request; well-known live platform, not independently confirmed further this session) | Free, self-serve launch listing for the Telegram-bot + web-app product itself, not a coupon page — no relevance gate to fail. | Profile/launch link, commonly nofollow on the launch page itself but the maker/company profile link is often followed — **not independently rel-checked this session; verify with the same `rel`-attribute method used on SaaSHub before counting it.** One-time traffic spike from a tech audience, not Saudi shoppers. | Low. |
| **MAGNiTT — magnitt.com/companies** | Root `magnitt.com` → 403 (bot-block); `/companies` path → **verified 200** | MENA startup/company database used by regional investors and press; already flagged as a target in `Claude_Memory/seo_authority_building.md`, not yet executed. DealPulse is a real operating Telegram+web product with users, a legitimate fit. | Company profile citation; `rel` attribute on the outbound website link is **unverified** — check it live once a profile exists, same discipline as the SaaSHub finding. | Medium (profile creation, minimum viable company data). |
| **BetaList — betalist.com** | Verified 200 | Pre-launch/launch directory, free tier exists, no reciprocal-link requirement. | Profile link, likely nofollow-by-default on free tier (unverified) — same-class asset as Product Hunt, worth doing once, not worth chasing hard. | Low. |
| **AlternativeTo — alternativeto.net** | curl → 403 (bot-block; well-known live platform) | Same directory class as SaaSHub — "alternative to [coupon app]" listings. Given the SaaSHub lesson (verified badge → dofollow, else nofollow), expect the same unverified-until-verified pattern here. | Likely nofollow initially; do not overinvest until the `rel` attribute is checked post-listing. | Low. |
| **Crunchbase — crunchbase.com** | Verified 200 | Already flagged in memory as "planned," status not confirmed complete. Standard company-profile citation, industry-agnostic. | Nofollow by common platform convention (not independently rel-checked here) — value is NAP-consistency/entity-graph, not link authority. | Low. |
| **Trustpilot** | curl → **000** (no response from this session's network — unverified, not "down") | Memory (`Claude_Memory/seo_authority_building.md`) claims this is already complete ("أول باكلينك مكتمل"). | **Cannot confirm from this session.** Given this project's own documented pattern of "claimed complete" diverging from "actually live" (the SaaSHub case, and the memory-vs-live discrepancy noted in the 2026-08-10 draft of this same file), a manual browser recheck of the actual Trustpilot business page is the right next step, not a re-list here. | N/A — verification task, not outreach. |
| **partner.visitsaudi.com** (Saudi Tourism Authority partner directory) | Verified 200 | Already identified as a target in `seo_authority_building.md`, not yet executed. `/calendar` covers national occasions (National Day, Founding Day) — a genuine tourism-adjacent angle, not a generic "deals site" pitch. | Unverified whether the partner listing carries a followed link — application-gated, outcome unknown until applied. | Medium (partner application). |

### Tier B — real named targets, unconfirmed submission mechanism (verify before spending effort)

| Target | Reachable? | Note |
|---|---|---|
| **Wamda — wamda.com** (leading MENA entrepreneurship media outlet) | Homepage verified 200; guessed path `/startups` → **404**, so the actual startup-directory URL structure is unconfirmed | Wamda both runs a startup database and publishes editorial features. A self-serve directory path wasn't found by guessing — this needs a manual site-map check, not a submission attempt on a wrong URL. |
| **ArabNet — arabnet.me** (MENA tech/startup ecosystem org, runs the Riyadh Digital Summit) | Verified 200 | Maintains a startup database tied to event/community registration; submission mechanism and `rel` outcome both unverified. |
| **Monsha'at / business.sa** (Saudi SME-support government ecosystem) | Both `monshaat.gov.sa` and `business.sa` verified 200 | The 2026-08-10 draft of this file referenced "Monsha'at-affiliated directories" as a category, without a confirmed submission mechanism. Confirming the domains resolve is **not** the same as confirming they run a public business-listing feature — that still needs a manual check before this is promoted to Tier A. |

### Tier C — digital-PR press targets (see Deliverable 3 for the pitch angle; listed here for the ranked view)

| Outlet | Reachable? | Profile |
|---|---|---|
| **Sabq — sabq.org** | Verified 200 | One of the most-read general Saudi news portals (not business-niche) — broadest realistic audience fit for a "how many stores are running White Friday deals right now" consumer-interest angle. |
| **Argaam — argaam.com** | Verified 200 | Leading Saudi financial/markets news site; covers retail-sector trends. High authority, requires a genuine journalist pitch and a real named contact this session does not have. |
| **Al-Eqtisadiah — aleqt.com** | Verified 200 | Major Saudi economic daily. Same profile as Argaam. |
| **Mubasher — mubasher.info** | Verified 200 | Pan-Arab financial news/wire covering the Saudi market. Whether it accepts inbound PR pitches vs. only paid wire distribution is **unverified** — check before pitching. |
| **Zawya — zawya.com** | Verified 200 | Refinitiv-owned Gulf business news outlet **that also sells a paid PR-wire distribution product.** ⚠️ Gate check: if the only path to coverage is Zawya's paid wire, that is a paid-placement mechanism and needs the same "how is this link paid for" scrutiny that killed the SellWithBoost offer — pursue only an editorial journalist pitch, not paid distribution. |
| **Entrepreneur ME — entrepreneur.com/en-ae** | Verified 200 | Pan-Gulf entrepreneurship magazine (UAE-based, covers Saudi startups). Startup-profile PR angle, separate from the retail-data hook — same class as MAGNiTT/Wamda, not the calendar hook. |
| **Gulf Business — gulfbusiness.com** | curl → 403 (bot-block; well-known live UAE business publication) | Same class as Entrepreneur ME. |

**Explicitly not pursued, per owner's standing rejection** (`Claude_Memory/seo_owned_channels_pivot.md`):
Reddit, Quora, and cold external-blogger seeding. Not re-proposed here even as an option.

---

## Deliverable 2 — Merchant-Partner Angle: the Natural, Non-Transactional Reason

The mistake to avoid is framing this as "please link to me" — that's a favour ask and reads as such. The
real, non-transactional reason a partner like **Salla** or **Zid** would link to DealPulse is that
**affiliate and ambassador programmes need public proof their economics work in order to recruit their next
round of affiliates** — and DealPulse already has an unusually complete data trail most of their affiliates
never bother building:

- **Salla** — 13 attributed orders, ~525 SAR, already proven (`Claude_Memory/salla_proven_converters.md`),
  plus a dedicated 12–19 article content hub already built for one Salla merchant (Bedinroom). Salla runs a
  "التسويق بالعمولة" affiliate programme it wants to grow; a real (if modest) conversion story with a
  content strategy behind it is exactly the kind of proof-of-concept Salla's own growth marketing wants to
  publish, because it recruits more affiliates like DealPulse into the programme. Pitch: "feature this as an
  affiliate case study" — a benefit to Salla's recruitment funnel, not a favour to DealPulse.
- **Zid** ("سفير زد" ambassador programme) — DealPulse is an enrolled ambassador with a completed 26-article,
  ~20,200-word content cluster anchored on `zid-platform-guide-saudi`. Ambassador programmes commonly publish
  ambassador spotlights for the same recruitment reason as Salla above. Zid's own team (contact "أماني" per
  `Claude_Memory/zid_affiliate_channel.md`) already reviewed and approved the content cluster once — that
  existing relationship is the entry point for this ask, not a cold pitch.
- **Boostiny** — accepted as Publisher #52131 (2026-08-06), a second review is pending before the final
  agreement is signed. CPA networks like Boostiny/ArabyAds sometimes run "meet our publishers" features to
  build advertiser trust in the network — worth asking **only after** the agreement is signed, since the
  relationship isn't fully live yet.
- **CodeMap** — coupon-only channel integrated into Salla's own app marketplace. If CodeMap or Salla's app
  store publishes "who uses this integration" case studies, the same ask applies.
- **Do not pursue DCM Network for this purpose** — memory flags it as a low-value channel whose account was
  previously locked for code scarcity, not a link asset.

The common thread: **every one of these is an existing paid commercial relationship, so the ask is "help you
recruit more people like me," not "do me a favour."** That framing is also what keeps it inside the
white-hat gate — there is no reciprocal link and no payment for placement on either side.

---

## Deliverable 3 — Digital-PR Angle Built on `/calendar`

`/calendar` is the only genuinely citable asset this site has: a live, auto-rotating Saudi sales-season
calendar with Hijri and Gregorian dates, now merging the **Ministry of Commerce's official season windows**
(sourced from mc.gov.sa) with DealPulse's own live merchant-count data. That combination — official
government dates plus a live private data layer — is a real original synthesis, not a repackaged list, which
is what makes it citable rather than just another seasonal roundup.

**The pitch structure that stays inside the white-hat gate:** offer a citation of live, verifiable data, not
a paid or reciprocal placement. Concretely, for each named outlet in Tier C above:

- **Sabq (broadest audience)**: "N stores currently running [season] discounts, counted live from our own
  database" — a consumer-interest data point, not a guest post ask.
- **Argaam / Al-Eqtisadiah (business-press angle)**: same data hook, framed for a retail-sector trend
  story rather than a consumer one — these outlets cover White Friday/national-holiday retail trends
  annually and need a sourced number each cycle.
- **Timing, not content, is the lever**: pitches land in the days coverage starts running, not before —
  National Day/Founding Day (September), pre-Ramadan, and the White Friday (November) cycle are the three
  windows.
- **Hard constraint carried over from the zero-fabrication rule**: the number in any pitch must be counted
  live from `master` at the moment of pitching, not pulled from memory or a prior snapshot. A stale or wrong
  number in a press pitch is worse than no pitch.

---

## Deliverable 4 — What to Expect, Honestly

At DA 1 with (per the working number above) **~3 real dofollow linking domains**, here is what the numbers
in this report can and cannot support:

- **What moves immediately and is real:** because the base is this close to zero, a single new dofollow
  link from any Tier A target genuinely **doubles or triples the raw linking-domain count** — this is not
  an inflated promise, it's arithmetic on a base of 3. Landing 3–5 of the Tier A items above (SaaSHub
  approval + one directory profile + one merchant-partner feature, realistically inside 60–90 days given
  the effort levels listed) would take the real dofollow count from ~3 to ~6–8, a genuine 2–3x increase in
  the measurable linking-domain graph.
- **What does not move on the same timeline:** DA/DR/AS are composite, non-linear scores, not raw link
  counts. **No source in this audit provides a link-count-to-authority-point conversion rate**, and stating
  one here would be fabrication. Expect DA to stay visually flat (1, maybe 2) even after several real new
  directory links land — directory-tier links are exactly the kind of link Moz/Ahrefs/Semrush weight lightly
  in their authority algorithms, which is consistent with 12 months of Bedinroom/Salla/etc. partnership work
  not having moved DA off 1 already.
- **What actually could move the score, and why it's slower and less certain:** one piece of real editorial
  press pickup (Tier C, Deliverable 3) from a high-authority Saudi domain like Argaam or Sabq would likely
  do more for DA than every directory link combined, because DR/DA weighting favors source authority far
  more than link count. But press pickup has a materially lower hit rate than a self-serve directory
  submission and no guaranteed timeline — budget for pitching across all three seasonal windows (Sept,
  pre-Ramadan, Nov) over the coming year rather than expecting one attempt to land.
- **Bottom line, stated plainly:** this report can defend "the linking-domain count roughly doubles or
  triples within a quarter if the Tier A list is executed." It cannot defend any specific DA/DR/AS number or
  a specific date by which one is reached — that would be a number this audit cannot support, and the
  project's standing rule is to not produce one.

---

## Backlink Health Score

**Still INSUFFICIENT DATA for a composite number — but coverage improved from 0/7 to 3/7 factors this
update.** The skill's own floor requires at least 4 of 7 weighted factors to have real data before producing
a number; this update does not clear that floor, so no score is produced.

| Factor | Weight | Data this update? |
|---|---|---|
| Referring domain count | 20% | **Yes** — Moz 1 / Ahrefs 158 (3 followed) / Semrush 34, reconciled above to a working number of ~3 real followed domains. Confidence 0.75 (secondhand, cross-tool-agreeing). |
| Link velocity trend | 10% | **Yes** — Moz's 12-month DA chart, flat at 1 from Sep 2025 to Aug 2026, is direct evidence of zero velocity (normally a DataForSEO-only factor; this is an accepted substitute since it's a direct historical measurement, not an inference). |
| Follow/nofollow ratio | 5% | **Yes** — Ahrefs: 3 of 158 referring domains followed (~1.9%). |
| Domain quality distribution | 20% | No — no DA/DR distribution across individual referring domains was supplied, only the aggregate counts above. |
| Toxic link ratio | 20% | No — a high nofollow ratio is not the same as a spam/toxicity measurement; no Moz Spam Score or equivalent was supplied. Do not conflate the two. |
| Anchor text naturalness | 15% | No. |
| Geographic relevance | 10% | No. |

**3 of 7 factors covered** (up from 0 of 7 in the 2026-08-10 draft), still under the 4-factor floor.
Producing a number here would still be fabrication dressed as measurement.

---

## Priority Recommendations

| Priority | Action | Why |
|---|---|---|
| Critical | Execute the Tier A list (Deliverable 1): push SaaSHub to approval, submit MAGNiTT + Product Hunt + BetaList profiles, and check the `rel` attribute on each resulting link using the same method that caught SaaSHub's nofollow status | From a base of ~3 real dofollow domains, this is the highest-certainty, lowest-effort way to double the measurable linking-domain count within a quarter |
| Critical | Manually re-verify the Trustpilot listing (curl returned no response this session — unverified, not confirmed broken) | Memory claims this link is already complete; this project has twice now found "claimed complete" diverging from "actually live" (SaaSHub, and the earlier draft of this same file) — do not carry an unverified claim forward a third time |
| High | Send the Salla and Zid "affiliate/ambassador case study" pitches described in Deliverable 2, using the existing relationships (13 attributed Salla orders; Zid's "أماني" contact who already reviewed the content cluster) | Natural, non-transactional ask riding an existing paid relationship — near-zero cold-outreach cost, and the only category of target here with a plausible near-term dofollow outcome from a domain more relevant than a generic directory |
| Medium | Time the `/calendar` data-hook press pitches (Deliverable 3) to Sabq/Argaam/Al-Eqtisadiah for the National Day (Sept), pre-Ramadan, and White Friday (Nov) news cycles, using a live-counted merchant number at the moment of each pitch | The only path in this report to a link from a domain with real, high, independently-earned authority — low hit-rate, so plan for three attempts across the year, not one |
| Medium | Confirm the Wamda startup-directory URL and the Monsha'at/business.sa submission mechanism before spending effort on either (Tier B) | Both domains are confirmed live; neither has a confirmed self-serve listing path — verify before investing, per this project's own "verify before act" rule |
| Low | Gate-check Zawya specifically: confirm any coverage path is editorial, not its paid PR-wire product, before pitching | Same "how is this link paid for" test that already killed the SellWithBoost offer — apply it before outreach, not after |

## Data Source Summary

| Source | Coverage | Confidence | Freshness |
|---|---|---|---|
| Moz / Ahrefs / Semrush (via orchestrating agent's brief) | DA/PA/DR/AS, referring-domain counts, 12-month DA trend | 0.75 (reported, cross-tool-agreeing, not self-executed this session) | Per brief, checked live "today" (2026-08-1x) |
| Common Crawl Web Graph | `in_crawl` presence, both host forms | **0.95** — this session's own live tool run | Quarterly release, checked 2026-08-10, same audit; source: https://commoncrawl.org/web-graphs |
| Live `curl` reachability probes (this session, 2026-08-11) | HTTP status of every named target in Deliverable 1 | 0.90 for the status code itself; explicitly **not** evidence of `rel`/dofollow status or submission-flow existence | Live, 2026-08-11 |
| Memory files (`saashub_directory_listing.md`, `seo_authority_building.md`, `domain_authority_plan.md`, `salla_affiliate_channel.md`, `zid_affiliate_channel.md`, `boostiny_publisher_channel.md`, `codemap_affiliate_channel.md`, `admitad_affiliate_setup.md`, `seo_white_hat_only.md`, `seo_owned_channels_pivot.md`) | Historical context, partner-channel status, white-hat gate rules | Not independently re-verified except where noted inline | Various dates, see inline citations |
| claude-seo tier-check tooling (`backlinks_auth.py`, `moz_api.py`) | N/A | N/A | **Not found in this repository** — confirmed via `Glob` (0 matches) — this session could not run the skill's own Tier 0-3 commands |

**Not duplicated here:** on-page/technical SEO (see `technical.md` in this same findings folder — 78/100,
sitemap/robots/security headers already verified) and content/E-E-A-T quality (`/seo content <url>`).

---

## Pre-Delivery Review

**Step 1 (automated validator):** `validate_backlink_report.py` was **not found in this repository**
(`Glob` search, 0 matches) — the mandatory automated validation step could not be run this session. This is
disclosed rather than silently skipped, per the "never fail silently" rule.

**Step 2 (manual checks, performed as a partial substitute):**
1. Every claim above carries a source label and a confidence figure — done throughout.
2. No inference is stated as fact: every unverified `rel`/submission-mechanism claim is explicitly marked
   "unverified" rather than assumed from the target's category.
3. Platform detection — not applicable to this report (no HTML-signal platform claims made).
4. Outbound/inbound consistency — not applicable (this is an outreach/target-list report, not a page audit);
   noted explicitly rather than skipped silently.
