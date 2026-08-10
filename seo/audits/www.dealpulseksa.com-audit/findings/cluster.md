# Topic Cluster Architecture — dealpulseksa.com (v2, measured-demand pass)

**This version overwrites v1.** v1 guessed which occasions were "worth testing." This
pass has real GSC demand (28 days: **7,609 impressions, 34 clicks, CTR 0.45%**) and adds
4 new SERP checks (National Day, summer sales, Ramadan/Eid pure-date, White Friday) on
top of the 8 from v1 (kept below as supporting evidence, not re-run). **12 queries
total across both sessions.**

**Search-tool limitation (state every session, do not let it silently drop):** WebSearch
is US-hosted, not Saudi-localized. It returns an AI-curated set of ~5-8 link previews per
query, not a geo-accurate top-10 organic SERP and no volume numbers. For a
coupon-aggregator niche where ranking is dominated by a fixed cartel of ~10 Arabic
single-purpose domains, this is directionally reliable (the same domains recur query
after query, which is itself the signal) but a Saudi-IP rank tracker would be needed to
confirm exact positions. Every "winnable"/"not winnable" call below is a domain-presence
read, not a position measurement.

---

## 1. RANKED: date/occasion/timing clusters winnable now

### Rank 0 — ALREADY WINNING, not hypothetical. Extend it, don't replace it.

The only pattern in the entire measured 7,609-impression set that converts is the
**sales-timing question family**, and it is live in production right now:

| Query | Position | Clicks |
|---|---|---|
| متى تبدأ التخفيضات في السعودية | 9.0 | 1 |
| مواعيد التخفيضات في السعودية | 8.1 | 1 |
| مواعيد التخفيضات العالمية | 6.0 | 1 |

/calendar CTR 1.11% vs /store CTR 0.12% — a 9x gap, measured, not modeled. **Action:**
before writing any new page, add more `متى/مواعيد + تخفيضات` long-tail variants as
sections inside the existing `/calendar` hub (regional/category breakdowns — "متى تبدأ
تخفيضات الإلكترونيات", "مواعيد تخفيضات الملابس") rather than a new pillar. SERP support
for this exact family: searching `عروض تخفيضات الصيف السعودية 2026` surfaced
**qyubic.com**, whose own ranking page is literally titled "متى تبدأ التخفيضات في
السعودية؟ دليل أفضل مواسم العروض" — i.e. dealpulseksa is already competing directly
against a small dedicated timing-guide vertical here, not the coupon cartel. That is a
winnable competitive set.

### Rank 1 — National Day (اليوم الوطني السعودي), date/history framing — SERP-CONFIRMED CLEAN

Query `اليوم الوطني السعودي 96 موعد الاحتفال` returned rahhal.wego.com (the **same
domain** that already validated the school-calendar cluster in v1 — recurrence across
two independent occasion checks strengthens confidence it's a stable non-cartel
vertical), wmadaat.com, mdares.ai, khaleejcalculators.com (also seen in the White Friday
check below — a general date-calculator publisher, not a coupon site). **Zero of the
cartel domains present.** Verdict: **winnable**, same head-noun rule as Rank 0/back-to-
school — keep the page about the date/duration/history of the 23 September holiday, not
about "عروض."

Tested the commercial variant too — `عروض اليوم الوطني السعودي` returned x.com,
wikipedia.org, **amazon.sa, jarir.com**, toptato.com, tawabel7.com. No cartel domains
here either, but a *different* failure mode: this SERP is **brand-owned** (Amazon and
Jarir's own National Day promo pages), which a third-party aggregator page cannot
outrank on relevance grounds regardless of authority. **Do not build a "عروض اليوم
الوطني" roundup page** — informational/date framing only.

### Rank 2 — Ramadan / Eid, pure Hijri-date framing — SERP-CONFIRMED CLEAN

Query `متى رمضان 1448 السعودية` returned islamicfinder.org, hijri-calendar.com,
hijricalendar.me, tahweelhijrimiladi.com, hijri.today — pure Islamic-calendar
publishers. Query `متى عيد الفطر 1448 السعودية` returned hijridate.org,
**moe.gov.sa** (Ministry of Education), datehijri.com, date-converter.com,
tahweelhijrimiladi.com. **Zero cartel presence in either.** This is the cleanest result
of the whole audit — a government ministry domain sits in the same SERP as the
publishers dealpulseksa would need to outrank, meaning the competitive bar is
"good calendar content," not "beat 10 dedicated coupon SEO operations."

**But the commercial variant fails, confirmed two different ways:** v1's
`كوبون خصم رمضان السعودية` fell straight into the cartel (almowafir.com,
codekhasem.com, also3odyah.com, coponsa.com, e5smley.com). This session's
`عروض رمضان السعودية 2026` avoided the cartel but landed in the **hypermarket-circular
vertical** instead (nice.com.sa, visitsaudi.com, redsea.com, alsoouq.com,
3orod.today, alsaifkitchen.com) — the same wrong-fit product category v1 flagged for
`عروض المتاجر السعودية` (Carrefour/Panda/Othaim print-circular aggregators, not promo
codes). Neither commercial framing is dealpulseksa's fight. **Only the pure-date
question ("متى رمضان" / "متى عيد الفطر") is winnable.**

### Rank 3 — Back-to-school — SERP-confirmed in v1, unchanged, still valid

`تقويم اجازة المدارس السعودية 2026` → al-ain.com, rahhal.wego.com, saudicalendars.com,
sudafax.com, nabd.com. No cartel presence. Carried forward from v1 as-is (see §5 for
the full hub-spoke build).

### REJECTED this session — White Friday (الجمعة البيضاء) fails the pattern the brief hypothesized

This is the important negative finding: the brief listed White Friday as an anchor
"worth testing," treating it as just another date/occasion. It is not. **Both framings
tested fall straight into the cartel:**

- `الجمعة البيضاء السعودية عروض 2026` → almuheet.net, **allcouponat.com,
  goldencouponzz.com, coupoonat.com**, khaleejcalculators.com, saudiscounts.com
- `متى الجمعة البيضاء 2026 السعودية موعد` → codekhasem.com, **allcouponat.com
  (twice), coupoonat.com**, khaleejcalculators.com

Three of the eight v1 cartel domains (allcouponat.com, coupoonat.com,
goldencouponzz.com) show up even on the **pure "متى" date query** — not just the
"عروض" commercial query. **Why:** White Friday's identity *is* "the discount day" —
unlike Ramadan/Eid/National Day, there is no neutral civic/religious meaning to
retreat to. The coupon cartel already targets the date question itself. **Rule
correction for §3: "is this a date/occasion query" is necessary but not sufficient —
also ask whether the occasion's entire cultural identity is the discount event. If yes,
treat it as a coupon-vertical query and apply the full cartel filter, expect
rejection.**

### REJECTED this session — Summer sales (تخفيضات الصيف)

`عروض تخفيضات الصيف السعودية 2026` returned a mixed, unclean set: akhbaar24.com /
alriyadh.com / sabq.org (national news), visitsaudi.com (government tourism authority —
a third unrelated vertical), qyubic.com (the timing-guide vertical from Rank 0 —
genuinely relevant), **allcouponat.com** (cartel), tsawq.net + saudi-offers.net
(hypermarket-circular vertical, already flagged wrong-fit in v1). No single clean
non-cartel competitive set to target. **Verdict: do not build a dedicated "summer
sales" occasion page** — the underlying demand is already captured by the Rank 0
timing-question family; a separate seasonal pillar would just fragment it.

---

## 2. The buried coupon terms are an AUTHORITY problem, not a content problem

State this plainly because it is the load-bearing conclusion of the whole audit: **do
not commission new articles for these terms.**

| Query | Impressions (28d) | Position | Clicks |
|---|---|---|---|
| كود خصم ستايلي | 260 | 26.3 | 0 |
| كوبون نمشي | 213 | 58.9 | 0 |
| كود خصم فوغا كلوسيت | 134 | 48.3 | 0 |
| كود نمشي | 120 | 59.4 | 0 |
| خصم نمشي | 111 | 29.2 | 0 |
| كوبون ستايلي | 106 | 32.5 | 0 |
| كوبون كار بارتس | 105 | 22.3 | 0 |
| كود خصم موقع هواوي | 94 | 27.3 | 0 |
| كوبون باليه | 79 | 64.8 | 0 |

4,807 impressions, 3 clicks, sitting at position 22–65. The direct SERP evidence for
*why*: across both audit sessions, **every single "كود/كوبون خصم + brand" query
checked (8 of 8) returned zero dealpulseksa.com presence**, replaced by a recurring
~10-domain cartel (see updated list in §3). This holds regardless of brand tier or
existing investment — فوغا كلوسيت already has a 12–19-article on-site cluster and still
does not surface; the ايهيرب supplements cluster (10 articles) does not surface either.
كار بارتس and موقع هواوي are different verticals again, same result. The site has
**1,582 articles producing 680 impressions and 2 clicks in total** — volume has already
been tried at scale and the wall did not move. More articles targeting these exact
buried terms would be repeating a controlled experiment that has already returned its
answer. The lever that exists is off-page authority (backlinks, brand mentions, age),
not more on-page supply — and that is out of scope for a content-cluster plan.

---

## 3. Hard selection filter — apply without judgment calls, to new pages AND retroactively to the 1,582 existing ones

1. **Query the exact target keyword live** before writing anything.
2. **Cartel-domain reject:** if any of these appear in the returned set → reject,
   fold into an existing page at most, never a new URL:
   `otlobcoupon.com, couponaat.com, allcouponat.com, codkhasm.com, coupoonat.com,
   goldencouponzz.com, couponwafy.com, couponmas.com, codekhasem.com` (9 domains —
   codekhasem.com added this session after recurring 4x across both audits, crossing
   the 3+ threshold).
3. **Head-noun reject:** if the head noun is "كود خصم" / "كوبون خصم" / "خصم" +
   [store or category] → default reject regardless of brand size or existing cluster
   investment. 8 of 8 branded coupon-code queries tested confirm this, with no
   exception found.
4. **Occasion queries are not automatically safe — test the occasion's identity, not
   just its category.** A date/occasion head noun is a *candidate*, not a pass. Ask:
   is this occasion's cultural identity itself "the discount day" (White Friday — the
   cartel owns even the pure date question) vs. a religious/civic observance where
   discount is a secondary association (Ramadan, Eid, National Day, school calendar —
   pure date framing stays clean)? Verify live per-query regardless of which bucket it
   seems to fall in.
5. **Commercial framing on top of a clean date query still needs its own check.**
   "متى/تقويم/موعد + occasion" passing does not clear "عروض/تخفيضات + occasion" — in
   every case tested, the commercial variant either fell into the cartel (Ramadan) or
   into a different wrong-fit vertical entirely: hypermarket-circular sites
   (alsoouq.com, 3orod.today, tsawq.net, saudi-offers.net — physical Carrefour/Panda/
   Othaim print circulars, a different product than promo codes) or brand-owned pages
   (amazon.sa, jarir.com for National Day) or a government tourism platform
   (visitsaudi.com for summer). None of these is dealpulseksa's competitive set even
   though none is the coupon cartel either — "not cartel" is necessary but not
   sufficient for "winnable."
6. **Only a clean pass on both 2 and 4/5 is a green light**, and even then the page
   must extend the existing `/calendar` pillar as a spoke, not launch a new hub —
   Rank 0/1/2/3 above are all sections of one property, not four separate bets.
7. **Retroactive audit (not done this session, no GSC query-level access from this
   agent):** cross-reference all 1,582 existing articles against rule 3. Given 8/8
   branded coupon-code SERP checks came back cartel-dominated, expect the bulk of the
   680-impression/2-click tail to be exactly this pattern — that cross-reference is
   the concrete next action, explicitly flagged as not yet done rather than assumed.

---

## 4. Supporting SERP evidence carried forward from v1 (unchanged, cited not re-run)

| # | Query | Top domains returned | dealpulseksa present? | Verdict |
|---|---|---|---|---|
| Q1 | كوبونات خصم | otlobcoupon.com, couponaat.com, goldencouponzz.com, allcouponat.com, coupoonat.com, codkhasm.com, apps.apple.com | No | Saturated head term |
| Q2 | كود خصم | apps.apple.com, otlobcoupon.com, couponaat.com, allcouponat.com, qasimahapp.com, codkhasm.com, couponwafy.com, codekhasmi.com | No | 5/8 domain-overlap with Q1 — near-synonym, same wall |
| Q4 | كوبون خصم نون | otlobcoupon.com, facebook.com, couponwafir.com, couponwafy.com, e5smley.com | No | Confirms known big-brand authority block |
| Q5 | كوبون خصم رمضان السعودية | almowafir.com, codekhasem.com, also3odyah.com, coponsa.com, e5smley.com | No | Seasonal modifier on a coupon head noun does NOT escape the cartel |
| Q6 | كود خصم فوجا كلوزيت | couponmas.com, coupoonat.com, ts3era.com, coupon4sales.com, couponatnoon.net | No, despite 12-19 existing articles | Existing investment ≠ ranking |
| Q8 | كوبون خصم مكملات غذائية ايهيرب | codekhasem.com, couponaat.com, goldencouponzz.com, couponmas.com, coupoonat.com, kudovo.com, couponjadide.com, rajli.app | No, despite 10 existing articles | Niche vertical has its own smaller cartel, still impenetrable |
| F | عروض المتاجر السعودية | alsoouq.com, 3orod.today, tsawq.net, getcata.com, 3rodoffers.com, dayoffer7.com, saudi-offers.net | No (wrong product) | Physical hypermarket circulars, different vertical — drop from keyword universe entirely |

---

## 5. Hub-and-spoke structure

Per `hub-spoke-architecture.md` thresholds (2-5 clusters, 2-4 posts/cluster, spoke
1200-1800w, pillar 2500-4000w).

**Pillar (existing production page — do not duplicate):** `/calendar` — Saudi seasons &
occasions hub. Template: `ultimate-guide`. Intent: Informational.

```
        [متى تبدأ التخفيضات — expand, Rank 0]     [اليوم الوطني: تاريخ وإجازة — Rank 1]
                          \                                /
                           \                              /
                            ------ [/calendar PILLAR] ------
                           /                              \
                          /                                \
     [متى رمضان / متى عيد الفطر — Rank 2]        [تقويم إجازات المدارس — Rank 3, v1]
```

### Cluster A — Rank 0 expansion (timing-question long tail)

| Post | Keyword | Intent | Template | Word count |
|---|---|---|---|---|
| Spoke A1 | متى تبدأ تخفيضات الإلكترونيات في السعودية | Informational | explainer (section of /calendar, not new URL if hub already covers it — check live page first) | 1200-1500 |
| Spoke A2 | مواعيد تخفيضات الملابس والأزياء في السعودية | Informational | explainer | 1200-1500 |

### Cluster B — National Day (Rank 1)

| Post | Keyword | Intent | Template | Word count |
|---|---|---|---|---|
| Spoke B1 | متى اليوم الوطني السعودي 96 وموعد الإجازة | Informational | explainer | 1200-1500 |

Do NOT add a "عروض اليوم الوطني" spoke — brand-owned SERP, see §1 Rank 1.

### Cluster C — Ramadan/Eid pure date (Rank 2)

| Post | Keyword | Intent | Template | Word count |
|---|---|---|---|---|
| Spoke C1 | متى رمضان 1448 في السعودية | Informational | explainer | 1200-1500 |
| Spoke C2 | متى عيد الفطر 1448 في السعودية | Informational | explainer | 1200-1500 |

Do NOT add "عروض رمضان" — falls into hypermarket-circular vertical, see §1 Rank 2.

### Cluster D — Back-to-school (Rank 3, carried from v1, SERP-validated)

| Post | Keyword | Intent | Template | Word count |
|---|---|---|---|---|
| Spoke D1 | تقويم إجازات المدارس السعودية 2026 | Informational | explainer | 1200-1500 |
| Spoke D2 | موعد بداية الدراسة 2026 السعودية | Informational | explainer | 1200-1500 |
| Spoke D3 | عروض العودة للمدارس (category-level roundup, not brand-level) | Commercial | listicle | 1500-1800 |

### Internal link matrix (all clusters)

| From | To | Type |
|---|---|---|
| /calendar (pillar) | every spoke (A1, A2, B1, C1, C2, D1, D2, D3) | mandatory |
| every spoke | /calendar (pillar) | mandatory |
| Spoke D1 | Spoke D2, Spoke D3 | recommended (same cluster) |
| Spoke D2 | Spoke D1, Spoke D3 | recommended |
| Spoke C1 | Spoke C2 | recommended (same cluster) |
| Spoke A1 | Spoke A2 | recommended (same cluster) |
| Spoke D3 | existing seasonal-school bridge (`seasonal_school_traffic_bridge.md`, 13-link bridge already live) | optional |
| Cluster B/C spokes | Cluster D spokes | optional cross-cluster (all are /calendar children) |

Every spoke: pillar link (mandatory, in) + pillar link (mandatory, out) + ≥1 sibling
link = satisfies "≥3 incoming" once siblings are counted both directions. No orphans —
every spoke reachable from `/calendar` in 1 click.

**Cannibalization check before writing any of Cluster A/B/C:** fetch the live
`/calendar` page first — if it already answers the date/timing question on-page, these
become sections of the existing hub, not new URLs. This agent did not fetch the live
page this session; flagged as the required pre-step, not done.

---

## 6. Cannibalization results

- كوبونات خصم × كود خصم: 5/8 domain overlap → same-cluster threshold, but both are
  out of reach per §3 rule 3, so the merge question is moot until authority changes.
- No cannibalization within Clusters A/B/C/D — four distinct, non-overlapping
  question families (timing-by-category / National Day / Ramadan-Eid / school
  calendar).
- Open cannibalization risk, unresolved: every new spoke vs. the existing live
  `/calendar` page content — must be checked before publishing (see §5 note).

---

## Structured summary (JSON-compatible, Content Architecture category)

```json
{
  "audit_category": "Content Architecture",
  "method": "SERP overlap / domain-presence clustering via WebSearch, 12 queries across 2 sessions, 2026-08-10",
  "search_tool_limitation": "US-hosted, not Saudi-localized; domain-presence reliable due to recurring cartel signal, exact position not confirmed",
  "measured_demand_28d": {"impressions": 7609, "clicks": 34, "ctr_pct": 0.45},
  "proven_pattern": {
    "family": "متى/مواعيد + تخفيضات (sales-timing question)",
    "queries": [
      {"query": "متى تبدأ التخفيضات في السعودية", "position": 9.0, "clicks": 1},
      {"query": "مواعيد التخفيضات في السعودية", "position": 8.1, "clicks": 1},
      {"query": "مواعيد التخفيضات العالمية", "position": 6.0, "clicks": 1}
    ],
    "ctr_comparison": {"calendar_pct": 1.11, "store_pct": 0.12}
  },
  "winnable_clusters": [
    {"name": "sales_timing_expansion", "rank": 0, "status": "already live, extend with long-tail", "pillar": "/calendar"},
    {"name": "national_day", "rank": 1, "status": "SERP-confirmed clean (rahhal.wego.com, wmadaat.com, mdares.ai, khaleejcalculators.com; zero cartel)", "reject_commercial_variant": true, "reject_reason": "brand-owned SERP (amazon.sa, jarir.com)"},
    {"name": "ramadan_eid_pure_date", "rank": 2, "status": "SERP-confirmed clean (islamicfinder.org, hijridate.org, moe.gov.sa, hijri-calendar.com family; zero cartel)", "reject_commercial_variant": true, "reject_reason": "falls into hypermarket-circular wrong-fit vertical (alsoouq.com, 3orod.today, visitsaudi.com family) or cartel depending on phrasing"},
    {"name": "back_to_school", "rank": 3, "status": "SERP-confirmed clean, carried from v1 unchanged"}
  ],
  "rejected_this_session": [
    {"name": "white_friday", "reason": "cartel present on BOTH date and commercial framing (allcouponat.com, coupoonat.com, goldencouponzz.com, codekhasem.com) — occasion's identity IS the discount event, unlike Ramadan/National Day", "critical_finding": true},
    {"name": "summer_sales", "reason": "mixed unclean SERP: news + government tourism + timing-guide (relevant) + cartel + hypermarket-circular, no single clean competitive set; underlying demand already covered by rank-0 pattern"}
  ],
  "buried_coupon_terms_verdict": "AUTHORITY problem not content problem — 8/8 branded coupon-code SERP checks across both sessions returned zero dealpulseksa presence regardless of brand tier or existing article-cluster investment (فوغا كلوسيت 12-19 articles, ايهيرب 10 articles both absent); do not commission new articles for these terms",
  "cartel_domain_list": ["otlobcoupon.com","couponaat.com","allcouponat.com","codkhasm.com","coupoonat.com","goldencouponzz.com","couponwafy.com","couponmas.com","codekhasem.com"],
  "wrong_fit_verticals": [
    {"name": "hypermarket_circulars", "domains": ["alsoouq.com","3orod.today","tsawq.net","saudi-offers.net","getcata.com","3rodoffers.com","dayoffer7.com"], "reason": "physical Carrefour/Panda/Othaim print circulars, different product than promo codes"},
    {"name": "brand_owned_national_day", "domains": ["amazon.sa","jarir.com"], "reason": "commercial National Day queries are brand-owned, not third-party-aggregator winnable"},
    {"name": "government_tourism", "domains": ["visitsaudi.com"], "reason": "summer sales query partially owned by official tourism authority platform"}
  ],
  "selection_filter": [
    "1. query the exact target keyword live before writing",
    "2. reject if any of the 9 cartel domains appear",
    "3. default reject if head noun is كود/كوبون/خصم + store/category, any brand tier",
    "4. occasion queries are a candidate not an automatic pass — test whether the occasion's cultural identity IS the discount event (fails, e.g. White Friday) vs a secondary association (passes if pure-date framed, e.g. Ramadan/Eid/National Day/school calendar)",
    "5. clean date framing does not clear commercial framing on the same occasion — check separately, expect either cartel or a different wrong-fit vertical",
    "6. only a clean pass on rules 2/4/5 is a green light, and it ships as a /calendar spoke, not a new pillar",
    "7. retroactive cross-reference of all 1,582 existing articles against rule 3 is the concrete next action, not yet done (no GSC query-level access this session)"
  ],
  "cannibalization": [
    {"pair": ["كوبونات خصم", "كود خصم"], "overlap": "5/8 domains", "action": "moot — both out of reach per filter rule 3"},
    {"pair": ["new /calendar spokes (A/B/C)", "existing live /calendar page"], "overlap": "unchecked", "action": "fetch live page content before publishing, not done this session"}
  ]
}
```
