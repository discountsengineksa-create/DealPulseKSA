# Topic Cluster Architecture — dealpulseksa.com (v3, page-level corrected pass)

**This version overwrites v2.** v2 summed query-level GSC rows, which Google truncates
for rare/low-volume queries — the orchestrator measured that this hid **41% of
impressions and 74% of clicks**. This pass uses only the page-level 28-day figures
supplied by the orchestrator (below) and adds live SERP verification of two new-ground
niches (car-diagnostic tools, school-administration templates) plus one new seasonal
occasion. Everything under "carried forward" from v2 is cited, not re-run, per the
orchestrator's instruction that it is already SERP-verified.

**Search-tool limitation, stated every session:** WebSearch is US-hosted, not
Saudi-localized. It returns an AI-curated ~6-9 link preview set per query, not a
geo-accurate top-10 organic SERP and no volume numbers. Domain-presence (does a known
competitor/cartel/incumbent show up) is directionally reliable because the same domains
recur query after query — that recurrence is itself the signal. Exact ranking position
is not confirmed by this tool; a Saudi-IP rank tracker would be needed for that.

## Real performance, page-level (28 days) — anchor for everything below

| Template | Impressions | Clicks | CTR | Pages | Notes |
|---|---|---|---|---|---|
| /blog | 3,250 | 50 | 1.54% | 565 | only 40 pages earn any click at all |
| /store | 6,693 | 17 | 0.25% | 49 | worst CTR of any template, most impression volume |
| /calendar | 1,859 | 38 | 2.04% | 1 | single page, second-best CTR |
| /category | 815 | 4 | 0.49% | — | |
| /c | 411 | 0 | 0.00% | 35 | zero clicks across every page |
| /national-day | 46 | 3 | **6.52%** | — | best CTR of any content page |
| /back-to-school | 59 | 2 | 3.39% | — | |
| /deals | 69 | 2 | 2.90% | — | |
| **Site total** | **12,957** | **132** | **1.02%** | — | |

Site total: **1,582 articles across the whole blog corpus produce 50 measured clicks
on 28 days** (per-page figures above) — volume has been tried at scale; it does not
convert impressions to clicks by itself. CTR, not impression count, separates the
winners (/calendar, /national-day, /back-to-school) from the losers (/store, /c).

---

## 1. Pattern 2 extension — how-to niches (highest-value new ground this session)

Both existing niche clusters already have deep on-site footprints, checked live against
`lib/blog.ts` before proposing anything, so nothing below duplicates an existing slug:

- **School-administration cluster: 10 existing articles** (`school-records-guide-saudi`
  — the 5-click, position-5.8 winner — plus `school-leader-records-guide-saudi`,
  `school-operational-plan-guide-saudi` — 3 clicks, position 8.8 —
  `school-meetings-minutes-guide-saudi`, `school-self-evaluation-guide-saudi`,
  `official-school-correspondence-guide-saudi`,
  `madrasati-distance-learning-templates-saudi`, `school-radio-templates-saudi`,
  `school-safety-plan-saudi`, `school-occasions-templates-saudi`). A separate 5-article
  "back to school shopping" set exists (`aliexpress-kids-school-backpacks-saudi-arabia`
  etc.) — different intent, not part of this cluster.
- **Car-diagnostic cluster: 69 existing AliExpress articles** — this is exhaustive
  already: every major multi-brand scan tool (Autel MK808/MS906/MK906, Xtool D9S Pro,
  Launch X431 Pad VII), every major single-brand tool (Toyota Techstream Mini VCI, BMW
  INPA/ISTA/ENET, Mercedes Star C4/C5/C6, Hyundai/Kia GDS Mobile), every mechanical
  tester (compression, smoke/vacuum-leak, coolant pressure, engine vacuum gauge, fuel
  pressure, timing light, automotive multimeter, borescope, brake bleeder, wheel
  alignment), all CarPlay/CarLinkit variants, and a further ~35 accessory/detailing/
  brake-parts articles. `carlinkit-5-setup-tutorial` (3 clicks) and
  `differential-oil-transfer-case` are both already live.

Given that density, the only defensible new ground is **brand/tool gaps in the
diagnostic-tool sub-niche specifically** (the sub-niche that actually earns clicks —
`toyota-techstream-mini-vci` and `hyundai-kia-gds-mobile` both convert; generic
accessory/detailing articles in the same corpus do not show up in the brief's winner
list). Five live SERP checks against that gap list:

| # | Candidate query | Top domains returned | Verdict | Rank |
|---|---|---|---|---|
| 1 | برنامج Forscan فحص سيارات فورد السعودية | `aliexpress.com` (own wiki article), `apkcafe.ae`, `amazon.sa`, `me.ford.com` (official Ford), `damaswiki.net`, `zebartech.com` (license reseller) | **Clean, real gap.** No independent Arabic tutorial site owns this query — only commerce/wiki/official pages. Ford (F-150, Explorer, Taurus) has real Saudi market share, unlike the next two negatives. Matches the exact pattern of the two proven winners (single-brand diagnostic tool + step-by-step tutorial). | **#1 — build first** |
| 2 | جهاز TPMS قراءة ضغط الإطارات السعودية | `noon.com`, `syarah.com/carsguide`, `arabdiag.sa`, `compu-car.com`, `launch-sa.com`, `autel-sa.com`, `autel-ksa.com` | **Reject.** Owned by the tool brands' own Saudi distributor sites (autel-sa.com **and** autel-ksa.com both present) — a brand-owned SERP, same failure mode as National Day's commercial variant, just for tools instead of occasions. | Reject |
| 3 | منظف حاقنات الوقود بالجهاز السعودية | `saco.sa`, `noon.com`, `advmotors.sa`, `jbr-ksa.com`, `qualityoil1.com`, `partspioneers.com`, `elitecar-sa.com` | **Reject, two reasons.** Wrong product type — a consumable chemical, not a diagnostic device, despite the query wording — and the SERP is owned by Saudi auto-parts e-commerce sites' own blog content (4 distinct parts-store domains), a wrong-fit vertical the same shape as the hypermarket-circular rejection in the coupon niche. | Reject |
| 4 | جهاز اعادة تعيين ضوء المحرك السعودية (check-engine-light reset) | `saudiauto.com.sa`, `syarah.com/carsguide`, `motorgy.com`, `noon.com`, `xtoolglobal.com` (brand's own Arabic blog) | **Reject.** `syarah.com/carsguide` is a large, established Saudi car-marketplace content arm — a real incumbent, not a thin competitor — plus a tool brand's own blog. Generic "why is my check-engine light on" is Syarah's territory. | Reject |
| 5 | جهاز VCDS فحص فولكس واجن أودي السعودية | 100% English/global: GitHub, `vcdspro.de`, `makeuseof.com`, `europaparts.com`, `oemdiagnostictools.com` | **Thin SERP, not a proven win.** Zero Arabic results at all — could mean zero competition, but more likely means near-zero Saudi search volume (VW/Audi are a small fraction of the KSA fleet vs. Toyota/Hyundai/Ford). Flag as **unproven demand**, not "clean and winnable" — SERP-thinness alone is not evidence of opportunity (see filter rule 8). | Low priority, needs a real demand check first |
| 6 | جهاز فحص شفروليه جي ام تك 2 السعودية (GM Tech2) | `alibaba.com`, `techroute66.com` (Egypt), `diamondegypt.com`, `amazon.eg` (not `.sa`) | **Same failure as #5** — no Saudi-specific presence at all, and the sources that do exist are Egyptian, not Saudi. Same "thin ≠ opportunity" flag. | Low priority, needs a real demand check first |

**Ranked recommendation for this cluster: build the Forscan/Ford diagnostic tutorial
next** (`aliexpress-forscan-ford-elm327-saudi-arabia` or similar), following the exact
structural pattern of `aliexpress-toyota-techstream-mini-vci-saudi-arabia` and
`aliexpress-hyundai-kia-gds-mobile-saudi-arabia` (both proven earners). Do not build
TPMS, injector-cleaner, or check-engine-light content — all three are incumbent- or
wrong-vertical-owned. Do not commission VW/Audi (VCDS) or GM (Tech2) content off SERP
thinness alone; that reads as "no competition," but for a niche vehicle segment in KSA
it more likely reads as "no demand" — verify actual search interest before writing,
this agent has no keyword-volume tool.

### School-administration: 3 adjacent topics tested

The competitive set here is structurally different from the coupon cartel — it's a
recurring cluster of **Saudi educational-template-sharing sites**
(`almanahj.com`, `edu-forms.com`, `beadaya.com`, `eduschool40.blog`, `arabforms.com`,
`tawthiqi.com`, `nmzjh.com`, `tahdiri.com`) that shows up across nearly every
admin-template query. **Critically, this is not a hard wall the way the coupon cartel
is** — the site's own `school-records-guide-saudi` (5 clicks, position 5.8) and
`school-operational-plan-guide-saudi` (3 clicks, position 8.8) already rank inside
exactly this competitive set. So the question for each candidate isn't "is a competitor
present" (yes, always) but "is there a differentiation anchor," the way the two
existing winners presumably have one.

| # | Candidate query | Top domains returned | Verdict | Rank |
|---|---|---|---|---|
| 1 | لائحة السلوك والمواظبة الطلابية السعودية نموذج | **`moe.gov.sa` (3 of 6 results — the actual official PDF regulation)**, `eduschool40.blog`, `asiaschool.com.sa` (a private school's own PDF upload) | **Winnable, with a specific angle.** The primary source lives directly on the Ministry's own domain, the same shape as the Ramadan/Eid pattern (`moe.gov.sa` co-occurring with independent publishers was still ruled winnable there). The page must be a **دليل تطبيق / شرح** (explainer / how school staff and parents apply the rule) — not an attempt to host or replace the regulation text itself. High real recurring demand: attendance/behavior policy is a live concern every semester for every parent and homeroom teacher, not a one-time template need. | **#1 — build first** |
| 2 | سجل الزيارة الصفية نموذج السعودية (classroom-visit log) | `almanahj.com`, `eduschool40.blog`, `arabforms.com`, `education-ksa.com` (forum), `edu-forms.com`, `tawthiqi.com` | **Winnable, same competitive set as the two proven winners**, but narrower audience — classroom-visit logs are used by supervisors/vice-principals, not every teacher, so expect it to land in the same 3-8 click range as the existing winners at best, not exceed it. | #2 |
| 3 | نموذج خطة علاجية مدرسية السعودية (remedial plan) | 9 distinct specialist template sites in one result set: `almanahj.com`, `edmodo.org` (Arabic clone site, not the real Edmodo), `tahdiri.com`, `faisaltheteacher.co`, `edu-forms.com`, `beadaya.com`, `nmzjh.com`, `d-abuomar.com`, `sijllati.abowsn.com` | **Lowest of the three.** Most crowded SERP tested this session (9 competitors vs. 3-6 for the others) and, unlike #1, there is no official-ministry-document anchor to differentiate an explainer around — it is a pure template query going head-to-head against dedicated template mills on their own turf. Not a hard reject, but do it last. | #3 |

**Ranked recommendation: build the لائحة السلوك والمواظبة explainer next**, anchored
explicitly to the official `moe.gov.sa` document (cite it, summarize it, add the
parent/teacher application angle it doesn't cover), then the classroom-visit-log
template, then the remedial-plan template last if resources remain.

---

## 2. Pattern 1 extension — seasonal (building on the already-verified set)

Carried forward, unchanged, not re-run: **Rank 0** sales-timing question family (live,
extend as `/calendar` sections) · **Rank 1** National Day pure-date (clean) / commercial
variant (brand-owned, rejected) · **Rank 2** Ramadan/Eid pure-date (clean) / commercial
variant (hypermarket-circular vertical, rejected) · **Rank 3** back-to-school (clean) ·
**Rejected**: White Friday (cartel owns even the pure-date query — the occasion's
identity IS the discount event) and generic summer sales (mixed unclean SERP).

### New this session — Founding Day (يوم التأسيس), a second clean civic occasion

Date/history query `يوم التأسيس السعودي تاريخ الاحتفال` returned `ar.wikipedia.org`,
`mofa.gov.sa` (Foreign Ministry), `spa.gov.sa` (Saudi Press Agency), `visitsaudi.com`
(tourism authority), plus two independent blogs (`madaproperties.sa`, `larochelle1.com`).
**Zero cartel presence.** This is the same structural pattern as National Day — official/
government domains plus small independent publishers, no coupon-aggregator competition.

The commercial variant was also tested and **fails the same way National Day's did**:
`عروض يوم التأسيس السعودي خصومات` returned `otlobcoupon.com` and `almowafir.com`
(**cartel**, 2 of the 9 tracked domains), `stc.com.sa` (brand-owned), `blackbox.com.sa`
(electronics retailer's own page), `elwatannews.com` (national news). **Do not build a
"عروض يوم التأسيس" page** — pure date/history framing only, exactly the National Day
rule.

Founding Day falls on 22 February, National Day on 23 September — together they give
full-year civic-occasion coverage for the `/calendar` hub, seven months apart, same
template as the existing National Day spoke.

### Correction to v2's Cluster A (timing-question long tail) — it is NOT automatically clean

v2 flagged `متى تبدأ تخفيضات الإلكترونيات في السعودية` as an untested extension of the
Rank-0 pattern and implicitly treated the whole "متى/مواعيد + category" family as safe
by extension. **Live-tested this session, it is not fully clean:**
`allcouponat.com` and `goldencouponzz.com` — 2 of the 9 tracked cartel domains — appear
in this exact SERP, alongside `maaal.com`/`ajel.sa` (legitimate Ministry-of-Commerce
news about the 2026 official discount season), `qyubic.com` (the same timing-guide
vertical already flagged as a relevant competitor at Rank 0), and one brand blog
(`sleepbox.com.sa`). **`www.dealpulseksa.com/calendar` itself already ranks in this
SERP** — direct, live confirmation that the query is already being captured by the
existing hub page. Combined with partial cartel presence, this is the right call for
two independent reasons, not one: **expand `/calendar`'s on-page content for this query
family, do not ship it as a separate spoke URL** — a new URL would compete against the
qyubic.com vertical and two cartel members simultaneously for a query the pillar already
ranks for.

---

## 3. Zero-click blog topic types — never repeat

The brief states 524 of the blog's zero-click articles as the population; the arithmetic
from the page-level table (565 total − 40 with-click ≥ 1) gives 525 — a 1-page
discrepancy, immaterial to the conclusion, flagged rather than silently resolved either
way. Cross-referencing the carried-forward SERP evidence (§4 of v2, unchanged) and this
session's content-quality audit (`findings/content.md`), the following topic *types*
should not be commissioned again anywhere in the corpus:

1. **`كود خصم` / `كوبون` + [any brand] articles**, regardless of brand size or existing
   cluster investment. 8/8 SERP checks across both audit sessions returned zero
   dealpulseksa.com presence, replaced by the same ~9-domain cartel — including
   فوغا كلوسيت (12-19 existing articles) and the ايهيرب supplements cluster (10 existing
   articles), both fully absent despite real on-site investment. This is an authority
   ceiling, not a content gap; more articles cannot close it.
2. **`/c` category-listing pages as a template**, independent of topic. All 35 existing
   pages earn zero clicks combined (0.00% CTR) — this is a template-level failure, not a
   topic-selection one; do not extend this template to new categories.
3. **`/store` FAQ pages at scale without per-store differentiation.** Measured at 0.25%
   CTR (worst of any template) against 6,693 impressions — the most exposure of any
   template with the worst conversion. The one sampled page (`/store/سويتر`) is 63 words,
   a verbatim-reusable two-question format ("كيف أستخدم كوبون [X]؟" / "هل كوبون [X]
   مجاني؟"), with no `Offer`/`FAQPage` schema. Do not add more stores to this template
   as-is; either add genuine per-store content or the pattern repeats at the next 49
   pages too.
4. **Commercial-intent framing on top of an otherwise-clean seasonal/occasion query**,
   confirmed failing on every civic occasion tested (National Day, Founding Day) and on
   Ramadan/Eid — each commercial variant lands in either the cartel or a different
   wrong-fit vertical (hypermarket circulars, brand-owned pages, telecom/retailer promo
   pages). The date/history framing of the same occasion is what earns clicks
   (/national-day: 6.52% CTR); the commercial framing of the same occasion is not a
   different intensity of the same opportunity, it is a different, worse SERP.
5. **Any occasion whose cultural identity is itself "the discount event"** (proven once,
   White Friday) — treat as coupon-vertical, not occasion-vertical, and expect the full
   cartel to already own the pure date question too, not just the commercial one.
6. **Generic informational car-maintenance topics with a large incumbent already
   established** (this session: check-engine-light explainers, owned by
   `syarah.com/carsguide`) and **tool/brand-distributor-owned product categories**
   (TPMS tools, owned by autel-sa.com/autel-ksa.com/launch-sa.com's own Saudi SEO) — both
   new failure modes this session, same shape as the brand-owned/hypermarket-circular
   rejections already established for occasions.

---

## 4. Hard selection filter — apply without judgment calls (new + carried-forward rules)

1. **Query the exact target keyword live** before writing anything — no keyword ships
   on the strength of an existing on-site cluster's investment alone (rule 3 in v2 was
   proven again this session: neither فوغا كلوسيت's 12-19 articles nor the two
   diagnostic-tool niches' 69+79 combined articles bought a pass on new adjacent terms
   that failed their own live check).
2. **Cartel-domain reject** (coupon/occasion queries only): if any of these 9 appear,
   reject outright, fold into an existing page at most, never a new URL —
   `otlobcoupon.com, couponaat.com, allcouponat.com, codkhasm.com, coupoonat.com,
   goldencouponzz.com, couponwafy.com, couponmas.com, codekhasem.com`.
3. **Head-noun reject**: "كود خصم" / "كوبون خصم" / "خصم" + [store/category] → default
   reject, any brand tier, any existing investment.
4. **Occasion queries are a candidate, not a pass — test cultural identity**: is the
   occasion's identity itself the discount event (White Friday — reject even the
   pure-date query) vs. a civic/religious observance where discount is secondary
   (Ramadan/Eid/National Day/Founding Day/school calendar — pure-date framing passes)?
5. **Commercial framing needs its own separate check even after date framing passes** —
   in every case tested across two sessions (Ramadan, National Day, Founding Day), the
   commercial variant fails, landing in the cartel, a hypermarket-circular vertical, or a
   brand/government-owned SERP. Never assume a clean date-query authorizes a matching
   "عروض + occasion" page.
6. **Brand/tool-distributor-owned reject** (new this session): if the SERP is dominated
   by the product/tool brand's own Saudi distributor domains (this session:
   autel-sa.com + autel-ksa.com + launch-sa.com for TPMS tools) or by auto-parts
   e-commerce stores' own blog content (injector cleaners), reject — this is the same
   shape as brand-owned/hypermarket-circular, generalized past the coupon niche.
7. **Large-incumbent reject** (new this session): if a single large, established
   vertical platform already visibly owns the generic informational framing of the topic
   (this session: `syarah.com/carsguide` for check-engine-light), reject the generic
   framing; a narrower, tool/brand-specific angle may still be viable and needs its own
   separate check.
8. **SERP-thinness is not evidence of opportunity by itself** (new this session, VCDS
   and GM Tech2 both returned almost no Saudi/Arabic results at all). Absence of
   competition can mean "open lane" or "no one searches this" — this agent has no
   keyword-volume tool to distinguish them. Do not greenlight from thinness alone;
   require either a real demand signal (Google Ads Keyword Planner is currently
   rejected/not integrated per `keyword_demand_ksa.md`, so use GSC query-level data or
   direct market-share reasoning — e.g. VW/Audi/GM's small share of the KSA vehicle
   fleet vs. Toyota/Hyundai/Ford) or treat as low priority.
9. **Recurring-specialist-competitor presence is not automatically a wall** (new this
   session, school-admin templates): unlike the coupon cartel, a recurring competitor
   set can be beatable if the site already has proven winners inside that exact
   competitive set. Check whether existing on-site articles already rank against the
   same competitor list before rejecting on presence alone — and prefer candidates with
   a differentiation anchor (an official primary-source document to explain/summarize)
   over pure template-vs-template competition.
10. **Only a clean pass on 2-9 as applicable is a green light**, and it ships as a spoke
    of the relevant existing pillar/cluster (`/calendar` for occasions, the diagnostic-
    tool sub-cluster for cars, the admin-template sub-cluster for schools) — not as a
    new hub. No new pillar is justified by this session's findings.
11. **Retroactive audit still not done** (carried from v2, unchanged): cross-referencing
    all 1,582 existing articles against rules 2-3 remains the concrete next action, not
    yet performed — no per-article GSC query-level access from this agent.

---

## 5. Cannibalization results

- No new cannibalization introduced by the two candidate winners this session
  (Forscan/Ford tutorial, لائحة السلوك explainer) — both target keywords are absent
  from the existing 69-article car cluster and 10-article school cluster (grep-verified
  against `lib/blog.ts` before proposing either).
- **Confirmed cannibalization risk, resolved this session**: `متى تبدأ تخفيضات
  الإلكترونيات في السعودية` — `/calendar` already ranks for this exact query (observed
  directly in the live SERP). A new spoke URL for this keyword would self-cannibalize
  the pillar. Resolution: expand `/calendar`'s on-page content, do not ship a new URL —
  corrects v2's untested assumption that this was a safe new spoke.
- Carried forward, unchanged: كوبونات خصم × كود خصم (5/8 domain overlap, moot — both
  out of reach per filter rule 3).

---

## 6. Hub-and-spoke additions (this session, appended to v2's `/calendar` structure)

Per the skill's thresholds (2-5 clusters, 2-4 posts/cluster, spoke 1200-1800w, pillar
2500-4000w). v2's `/calendar` pillar and Clusters A-D stand as documented there; this
session adds one occasion spoke and opens two new pillars for the how-to niches
(car-diagnostic and school-administration already exist as de facto pillars — the
existing highest-traffic hub article in each, `aliexpress-cars-guide-saudi-arabia` and
implicitly the records/operational-plan pair — spokes attach to those, not to
`/calendar`).

### Cluster E — Founding Day (new, same shape as Cluster B/National Day)

| Post | Keyword | Intent | Template | Word count |
|---|---|---|---|---|
| Spoke E1 | يوم التأسيس السعودي: التاريخ وموعد الإجازة | Informational | explainer | 1200-1500 |

Do NOT add "عروض يوم التأسيس" — cartel + brand-owned SERP, confirmed this session.
Link matrix: `/calendar` ↔ Spoke E1 mandatory both directions (same pattern as B1/C1/D1).

### Cluster F — Car-diagnostic tool gap (new pillar: `aliexpress-cars-guide-saudi-arabia`, existing)

| Post | Keyword | Intent | Template | Word count | Rank |
|---|---|---|---|---|---|---|
| Spoke F1 | فحص وبرمجة سيارات فورد بجهاز Forscan في السعودية | Informational/Commercial | tutorial/review (matches `aliexpress-toyota-techstream-mini-vci` pattern) | 1200-1800 | Build first |

Do NOT build TPMS, fuel-injector-cleaner, or check-engine-light-reset content (§1
rejects). VW/Audi (VCDS) and GM (Tech2) need a demand check before consideration, not a
content commission.

### Cluster G — School-administration gap (new pillar: `school-records-guide-saudi`, existing, the proven top performer)

| Post | Keyword | Intent | Template | Word count | Rank |
|---|---|---|---|---|---|---|
| Spoke G1 | لائحة السلوك والمواظبة الطلابية في السعودية: دليل شرح وتطبيق | Informational | explainer, anchored/cited to `moe.gov.sa` | 1200-1500 | Build first |
| Spoke G2 | سجل الزيارة الصفية: نموذج وشرح الاستخدام | Informational | explainer | 1200-1500 | Build second |

Remedial-plan template (§1, rank #3) held back — most crowded SERP tested, no
differentiation anchor, build only if G1/G2 prove out.

### Internal link matrix (additions only)

| From | To | Type |
|---|---|---|
| `/calendar` (pillar) | Spoke E1 | mandatory, both directions |
| `aliexpress-cars-guide-saudi-arabia` (car pillar) | Spoke F1 | mandatory, both directions |
| Spoke F1 | `aliexpress-toyota-techstream-mini-vci-saudi-arabia`, `aliexpress-hyundai-kia-gds-mobile-saudi-arabia` | recommended (same diagnostic-tool sub-cluster, both proven earners) |
| `school-records-guide-saudi` (school pillar) | Spoke G1, Spoke G2 | mandatory, both directions |
| Spoke G1 | Spoke G2 | recommended (same cluster) |
| Spoke G1, G2 | `school-operational-plan-guide-saudi` | optional cross-link (same cluster, different existing spoke) |

Every new spoke: pillar link in + pillar link out + ≥1 sibling link = satisfies "≥3
incoming" once siblings are counted both directions. No orphans.

---

## Structured summary (JSON-compatible, Content Architecture category)

```json
{
  "audit_category": "Content Architecture",
  "version": "v3, page-level corrected pass",
  "method": "SERP overlap / domain-presence clustering via WebSearch, 10 new queries this session (5 car-diagnostic, 3 school-admin, 2 seasonal), plus carried-forward v2 evidence (12 queries)",
  "search_tool_limitation": "US-hosted, not Saudi-localized; domain-presence reliable due to recurring competitor signal, exact position not confirmed, no volume data",
  "real_performance_28d_page_level": {
    "site_total": {"impressions": 12957, "clicks": 132, "ctr_pct": 1.02},
    "blog": {"impressions": 3250, "clicks": 50, "ctr_pct": 1.54, "pages": 565, "pages_with_any_click": 40},
    "store": {"impressions": 6693, "clicks": 17, "ctr_pct": 0.25, "pages": 49},
    "calendar": {"impressions": 1859, "clicks": 38, "ctr_pct": 2.04, "pages": 1},
    "category": {"impressions": 815, "clicks": 4, "ctr_pct": 0.49},
    "c": {"impressions": 411, "clicks": 0, "ctr_pct": 0.00, "pages": 35},
    "national_day": {"impressions": 46, "clicks": 3, "ctr_pct": 6.52},
    "back_to_school": {"impressions": 59, "clicks": 2, "ctr_pct": 3.39},
    "deals": {"impressions": 69, "clicks": 2, "ctr_pct": 2.90},
    "correction_note": "v2 used query-level GSC rows, which Google truncates for rare queries -- 41% of impressions and 74% of clicks were hidden; this version uses page-level figures only"
  },
  "how_to_niche_extension": {
    "existing_footprint": {"car_diagnostic_articles": 69, "school_admin_articles": 10, "verified_via": "grep against lib/blog.ts before proposing new topics"},
    "car_diagnostic_candidates": [
      {"query": "برنامج Forscan فحص سيارات فورد السعودية", "verdict": "winnable, build first", "domains": ["aliexpress.com","apkcafe.ae","amazon.sa","me.ford.com","damaswiki.net","zebartech.com"], "reasoning": "no independent Arabic tutorial competitor, real Ford market share in KSA, matches proven Toyota-Techstream/Hyundai-Kia-GDS pattern"},
      {"query": "جهاز TPMS قراءة ضغط الإطارات السعودية", "verdict": "reject", "domains": ["noon.com","syarah.com","arabdiag.sa","compu-car.com","launch-sa.com","autel-sa.com","autel-ksa.com"], "reasoning": "brand-distributor-owned SERP"},
      {"query": "منظف حاقنات الوقود بالجهاز السعودية", "verdict": "reject", "domains": ["saco.sa","noon.com","advmotors.sa","jbr-ksa.com","qualityoil1.com","partspioneers.com"], "reasoning": "wrong product type (consumable) + auto-parts-store-owned SERP"},
      {"query": "جهاز اعادة تعيين ضوء المحرك السعودية", "verdict": "reject", "domains": ["saudiauto.com.sa","syarah.com","motorgy.com","xtoolglobal.com"], "reasoning": "large established incumbent (syarah.com/carsguide) + brand blog"},
      {"query": "جهاز VCDS فحص فولكس واجن أودي السعودية", "verdict": "low priority, unproven demand", "domains": ["github.com","vcdspro.de","makeuseof.com","europaparts.com","oemdiagnostictools.com"], "reasoning": "zero Arabic/Saudi presence -- thin SERP, not confirmed opportunity, likely low VW/Audi market share in KSA"},
      {"query": "جهاز فحص شفروليه جي ام تك 2 السعودية", "verdict": "low priority, unproven demand", "domains": ["alibaba.com","techroute66.com","diamondegypt.com","amazon.eg"], "reasoning": "same thinness flag as VCDS, sources are Egyptian not Saudi"}
    ],
    "school_admin_candidates": [
      {"query": "لائحة السلوك والمواظبة الطلابية السعودية نموذج", "verdict": "winnable, build first", "domains": ["moe.gov.sa","eduschool40.blog","asiaschool.com.sa"], "reasoning": "official MOE primary-source document present, same pattern as Ramadan/Eid; needs explainer/application framing not primary-doc-hosting framing; perennial live demand every semester"},
      {"query": "سجل الزيارة الصفية نموذج السعودية", "verdict": "winnable, build second", "domains": ["almanahj.com","eduschool40.blog","arabforms.com","education-ksa.com","edu-forms.com","tawthiqi.com"], "reasoning": "same competitive set as proven on-site winners, narrower audience (supervisors not all teachers)"},
      {"query": "نموذج خطة علاجية مدرسية السعودية", "verdict": "lowest of three, build last", "domains": ["almanahj.com","edmodo.org","tahdiri.com","faisaltheteacher.co","edu-forms.com","beadaya.com","nmzjh.com","d-abuomar.com","sijllati.abowsn.com"], "reasoning": "most crowded SERP tested (9 competitors), no primary-source anchor to differentiate around"}
    ],
    "key_finding": "school-admin competitor set (Saudi educational-template-sharing sites) is NOT a hard wall like the coupon cartel -- site's own school-records-guide-saudi (5 clicks, pos 5.8) and school-operational-plan-guide-saudi (3 clicks, pos 8.8) already rank inside this exact competitive set, so presence of a recurring competitor is not sufficient grounds for rejection the way cartel presence is"
  },
  "seasonal_extension": {
    "new_clean_occasion": {"name": "founding_day", "date_query": "يوم التأسيس السعودي تاريخ الاحتفال", "domains_clean": ["ar.wikipedia.org","mofa.gov.sa","spa.gov.sa","visitsaudi.com","madaproperties.sa","larochelle1.com"], "verdict": "winnable, pure date/history framing, same pattern as national_day"},
    "commercial_variant_confirmed_failing": {"query": "عروض يوم التأسيس السعودي خصومات", "domains": ["otlobcoupon.com","almowafir.com","stc.com.sa","blackbox.com.sa","elwatannews.com"], "cartel_present": true, "verdict": "reject, same rule as national_day commercial variant"},
    "correction_to_v2": {
      "claim_corrected": "v2's Cluster A (متى تبدأ تخفيضات الإلكترونيات) was assumed safe by extension of the Rank-0 pattern, untested",
      "live_test_result": {"query": "متى تبدأ تخفيضات الإلكترونيات في السعودية", "domains": ["maaal.com","ajel.sa","qyubic.com","sleepbox.com.sa","allcouponat.com","goldencouponzz.com","dealpulseksa.com/calendar"], "cartel_present": true, "own_page_already_ranks": true},
      "resolution": "expand /calendar on-page content for this query family, do not ship as a new spoke URL -- partial cartel presence AND the pillar already ranks for this exact query"
    }
  },
  "never_repeat_topic_types": [
    "كود خصم / كوبون + any brand articles, any brand size or existing investment (authority ceiling, 8/8 SERP checks confirm)",
    "/c category-listing template, independent of topic (0.00% CTR across all 35 pages, template-level failure)",
    "/store FAQ pages at scale without per-store differentiation (0.25% CTR, worst template, 63-word thin content, verbatim-reusable 2-question format, no Offer/FAQPage schema)",
    "commercial framing layered on an otherwise-clean seasonal/occasion query (fails on National Day, Founding Day, Ramadan/Eid -- confirmed on every civic occasion tested)",
    "occasions whose cultural identity IS the discount event (White Friday -- cartel owns even the pure date query)",
    "generic informational topics already owned by a large incumbent (syarah.com/carsguide for check-engine-light) or by tool/parts-brand distributor SEO (TPMS, injector cleaners)"
  ],
  "selection_filter_v3": [
    "1. query the exact target keyword live before writing, regardless of existing cluster investment",
    "2. reject if any of the 9 cartel domains appear (coupon/occasion queries)",
    "3. default reject if head noun is كود/كوبون/خصم + store/category, any brand tier",
    "4. occasion queries: test whether the occasion's cultural identity IS the discount event (reject, e.g. White Friday) vs secondary association (pass if pure-date framed, e.g. Ramadan/Eid/National Day/Founding Day/school calendar)",
    "5. commercial framing needs its own separate check even after date framing passes -- never assumed clean by association",
    "6. new: reject if SERP is owned by the product/tool brand's own Saudi distributor domains or by vertical retailers' own blog content",
    "7. new: reject generic informational framing already owned by a large established incumbent platform; a narrower brand/tool-specific angle may still need its own separate check",
    "8. new: SERP-thinness (near-zero Arabic/Saudi results) is not evidence of opportunity by itself -- distinguish 'open lane' from 'no search volume' via GSC data or market-share reasoning before commissioning, this agent has no keyword-volume tool",
    "9. new: a recurring specialist-competitor set is not automatically a wall the way the coupon cartel is -- check whether existing on-site articles already rank inside that same competitive set before rejecting on presence alone; prefer candidates with a differentiation anchor (an official primary-source document) over pure template-vs-template competition",
    "10. only a clean pass ships as a spoke of the relevant existing pillar/cluster, never a new hub",
    "11. retroactive cross-reference of all 1,582 existing articles against rules 2-3 remains the concrete next action, still not done (no per-article GSC query-level access this session)"
  ],
  "cannibalization": [
    {"pair": ["متى تبدأ تخفيضات الإلكترونيات (candidate new spoke)", "/calendar (existing pillar, already ranks live)"], "action": "confirmed this session -- expand pillar on-page content, do not ship as new URL"},
    {"pair": ["كوبونات خصم", "كود خصم"], "overlap": "5/8 domains", "action": "moot -- both out of reach per filter rule 3, carried from v2"}
  ],
  "new_clusters": [
    {"name": "founding_day", "cluster_id": "E", "pillar": "/calendar", "spokes": [{"keyword": "يوم التأسيس السعودي: التاريخ وموعد الإجازة", "intent": "informational", "template": "explainer", "word_count": "1200-1500"}]},
    {"name": "car_diagnostic_gap", "cluster_id": "F", "pillar": "aliexpress-cars-guide-saudi-arabia", "spokes": [{"keyword": "فحص وبرمجة سيارات فورد بجهاز Forscan في السعودية", "intent": "informational_commercial", "template": "tutorial_review", "word_count": "1200-1800", "priority": 1}]},
    {"name": "school_admin_gap", "cluster_id": "G", "pillar": "school-records-guide-saudi", "spokes": [
      {"keyword": "لائحة السلوك والمواظبة الطلابية في السعودية: دليل شرح وتطبيق", "intent": "informational", "template": "explainer_anchored_to_moe_gov_sa", "word_count": "1200-1500", "priority": 1},
      {"keyword": "سجل الزيارة الصفية: نموذج وشرح الاستخدام", "intent": "informational", "template": "explainer", "word_count": "1200-1500", "priority": 2}
    ]}
  ]
}
```
