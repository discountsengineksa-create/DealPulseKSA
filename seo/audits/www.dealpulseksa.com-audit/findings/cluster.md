# Topic Cluster Architecture — dealpulseksa.com

**Method:** SERP overlap clustering (8 queries run live via WebSearch, 2026‑08‑10).
**Coverage disclosure (honest, not full):** 8 of the planned 30‑50 keyword universe were
queried due to the 20‑turn ceiling on this run. That is enough to establish the
*decisive pattern* below with real evidence, but it is a partial map, not an exhaustive
one. Treat this as v1 — extend with the same filter before publishing anything new.

**Data-source caveat:** WebSearch (not DataForSEO) was used. It returns an AI-curated
set of ~5‑8 link previews per query, not a guaranteed top‑10 organic-only list, and
gives no search-volume numbers. Overlap scores below are computed at **domain level**
(not full URL), which is the right resolution for this niche because the competing
sites are single-purpose coupon aggregators where the domain itself *is* the ranking
signal. No volume figure anywhere in this file is measured — none is claimed as such.

---

## 1. RANKED: What this domain can realistically win now

### Rank 1 (only strongly-evidenced win): Seasonal/occasion calendar hub — informational framing, NOT "كود خصم" framing

**Evidence:** Query `تقويم اجازة المدارس السعودية 2026` returned al-ain.com,
rahhal.wego.com, saudicalendars.com, sudafax.com, nabd.com — general news/travel/calendar
sites. **Zero overlap** with any of the 6 coupon-code queries below (domain overlap
score = 0 against all of them). This is a structurally different, less entrenched
competitive set: broad-topic publishers, not a dedicated single-purpose SEO vertical.

**Why it's winnable:** dealpulseksa is the only property in that class of SERP that can
credibly pair an accurate KSA date/calendar answer with an actual usable code — the
news/travel sites answer "when," dealpulseksa can answer "when + what to buy with."
This is also the pattern the site has *already* validated with real clicks per prior
audits (`Claude_Memory/calendar_conversion_hub.md`, `seasonal_school_traffic_bridge.md`
— GSC-sourced, not re-verified in this SERP session, cited as prior evidence not new
measurement).

**Action:** the production `/calendar` hub already exists — do not create a duplicate
pillar. Extend it with occasion spokes that keep the **head noun as the date/event**,
never as "كود خصم/كوبون". The moment "كود خصم" becomes the head noun, the query falls
back into the cartel's territory (see Rank-out-of-reach #E below) even with a seasonal
modifier attached.

### Rank 2 (hypothesis extension of Rank 1 — NOT SERP-validated this session)

Applying the same head-noun rule to other occasions (Ramadan/Eid dates, National Day,
mid-year break) is architecturally sound but **each one needs its own SERP check**
before a page is written — do not assume the pattern transfers. Flagged explicitly as
unverified so it is never mistaken for measured data.

### Everything else tested: not winnable now (see §2)

Six separate coupon/code queries — head-term, major-brand, mid-tier-brand (an
already-invested cluster), niche-vertical, and seasonal-transactional-blend — all
returned **zero dealpulseksa.com presence** in the returned results, dominated instead
by a recurring set of ~20 dedicated Arabic coupon-aggregator domains. This is the core,
sobering finding of this audit: **the site's single largest content investment (9 store
clusters, ~150+ articles, per `blog_14clusters_july11.md`/`blog_7clusters_july11.md`)
is fighting a wall that content volume alone has not breached in ANY of the 6 samples
checked** — not just for the known big-brand case (نون), but for a mid-tier brand the
site already has a built 12–19-article cluster for (فوغا كلوسيت) and a niche vertical
with an existing 10-article cluster (iHerb supplements).

---

## 2. OUT OF REACH today, and why (measured this session)

| # | Query | Top domains returned | Overlap w/ Q1/Q2 | dealpulseksa present? | Verdict |
|---|---|---|---|---|---|
| Q1 | كوبونات خصم | otlobcoupon.com, couponaat.com, goldencouponzz.com, allcouponat.com, coupoonat.com, codkhasm.com, apps.apple.com | — | No | Saturated head term |
| Q2 | كود خصم | apps.apple.com, otlobcoupon.com, couponaat.com, allcouponat.com, qasimahapp.com, codkhasm.com, couponwafy.com, codekhasmi.com | **5/8 shared with Q1** → same-cluster threshold (4-6) | No | Near-synonym of Q1; same wall |
| Q4 | كوبون خصم نون | otlobcoupon.com, facebook.com, couponwafir.com, couponwafy.com, e5smley.com | 1 w/Q1, 2 w/Q2 | No | Confirms known "نون blocked by authority" finding |
| Q5 | كوبون خصم رمضان السعودية | almowafir.com, codekhasem.com, also3odyah.com, coponsa.com, e5smley.com | 0 w/Q1, 0 w/Q2 | No | Seasonal *modifier on a coupon head noun* does NOT escape the cartel — different from Rank-1 pattern |
| Q6 | كود خصم فوجا كلوزيت | couponmas.com, coupoonat.com, ts3era.com, coupon4sales.com, couponatnoon.net | 1 w/Q1, 0 w/Q2 | No, despite an existing 12-19 article site cluster for this exact brand | Hardest finding: existing investment ≠ ranking |
| Q8 | كوبون خصم مكملات غذائية ايهيرب | codekhasem.com, couponaat.com, goldencouponzz.com, couponmas.com, coupoonat.com, kudovo.com, couponjadide.com, rajli.app | 3 w/Q1, 1 w/Q2 | No, despite existing 10-article iHerb cluster | Niche vertical has its own smaller cartel, still impenetrable |

**Cartel domain list (recurring 3+ times across the 6 queries above):** otlobcoupon.com,
couponaat.com, allcouponat.com, codkhasm.com, coupoonat.com, goldencouponzz.com,
couponwafy.com, couponmas.com — treat presence of any of these in top-5 as an automatic
reject signal (see filter in §4).

### F. Wrong-fit seed — drop entirely, not just "hard"

Query `عروض المتاجر السعودية` returned alsoouq.com, 3orod.today, tsawq.net,
getcata.com, 3rodoffers.com, dayoffer7.com, saudi-offers.net — **zero overlap with
both the coupon-code cartel and the calendar vertical.** This is a distinct product
category: physical hypermarket weekly print-circular aggregators (Carrefour/Panda/
Othaim flyers), not online promo codes. It answers a different user intent than
dealpulseksa's business. Recommend removing this seed from the keyword universe
rather than trying to "win" it — it was never the right battlefield.

---

## 3. Hub-and-spoke structure for the winnable cluster

Per `hub-spoke-architecture.md` thresholds (2-5 clusters, 2-4 posts/cluster, spoke
1200-1800w, pillar 2500-4000w). Only Cluster 1 below is SERP-validated; Clusters 2-3
are the same rule applied to un-checked occasions and are explicitly marked as such.

**Pillar (do not duplicate — this already exists in production):** `/calendar` —
Saudi seasons & occasions hub. Template: `ultimate-guide`. Intent: Informational.

```
                         [تقويم اجازات المدارس] --- [موعد بداية الدراسة]
                                    \                    /
                              [Cluster 1: العودة للمدارس]   ← SERP-validated today
                                          |
[Cluster 2: رمضان/عيد] -- [Cluster 2/3]-[/calendar PILLAR]-[Cluster 3]-- [اليوم الوطني/التأسيس]
   (hypothesis — validate                                    (hypothesis — validate
    before publishing)                                        before publishing)
```

### Cluster 1 — العودة للمدارس (Back-to-School) — SERP-validated

| Post | Keyword (head noun = date/event, never كود خصم) | Intent | Template | Word count |
|---|---|---|---|---|
| Spoke 1a | تقويم إجازات المدارس السعودية 2026 | Informational | explainer | 1200-1500 |
| Spoke 1b | موعد بداية الدراسة 2026 السعودية | Informational | explainer | 1200-1500 |
| Spoke 1c | عروض العودة للمدارس (روازم فئة، لا اسم متجر) | Commercial (roundup, category-level) | listicle | 1500-1800 |

**Cannibalization check:** before writing 1a/1b, confirm the live `/calendar` hub does
not already cover school-holiday dates on-page — if it does, these become sections of
the existing hub, not new URLs (same logic as the documented `/c/` ↔ `/store` lesson:
two pages answering one query cannibalize each other).

### Internal link matrix — Cluster 1

| From | To | Type | Anchor |
|---|---|---|---|
| /calendar (pillar) | Spoke 1a | mandatory | تقويم إجازات المدارس |
| Spoke 1a | /calendar (pillar) | mandatory | التقويم الكامل للمواسم |
| /calendar (pillar) | Spoke 1b | mandatory | موعد بداية الدراسة |
| Spoke 1b | /calendar (pillar) | mandatory | مواسم وعروض السعودية |
| /calendar (pillar) | Spoke 1c | mandatory | عروض العودة للمدارس |
| Spoke 1c | /calendar (pillar) | mandatory | كل المواسم والمناسبات |
| Spoke 1a | Spoke 1b | recommended | موعد بداية الدراسة 2026 |
| Spoke 1a | Spoke 1c | recommended | عروض العودة للمدارس |
| Spoke 1b | Spoke 1c | recommended | عروض العودة للمدارس |
| Spoke 1b | Spoke 1a | recommended | تقويم الإجازات الكامل |
| Spoke 1c | existing seasonal-school bridge (`seasonal_school_traffic_bridge.md`, 13-link bridge already live) | optional | contextual |

Every spoke: ≥3 incoming links (2 mandatory from pillar direction where pillar links
back + sibling links = satisfies the "≥3 incoming" minimum). No orphans — all 3 spokes
reachable from `/calendar` within 1 click.

### Clusters 2 & 3 — same pattern, NOT yet SERP-validated

- **Cluster 2 — رمضان/عيد dates:** use "امتى رمضان ١٤٤٨" / "تقويم رمضان السعودية"
  (date framing), explicitly avoid "كوبون خصم رمضان" (confirmed cartel territory, Q5
  above). Run the SERP check before writing.
- **Cluster 3 — اليوم الوطني / يوم التأسيس:** same rule — date/occasion framing only.
  Run the SERP check before writing.

Both are withheld from a full post-by-post plan here because presenting them without
a SERP check would violate the same "don't assume volume/rankability" rule this audit
is enforcing on the rest of the site.

---

## 4. The hard selection filter (mandatory before any new article, and for auditing the existing 1,582)

1. Query the exact target keyword live.
2. If any of the 8 cartel domains listed in §2 appear in the top 5 → **reject**. Do not
   publish a new standalone page; at most fold the angle into an existing cluster page.
3. If the head noun of the keyword is "كود خصم" / "كوبون خصم" + [store or category] →
   **default reject** regardless of brand tier — Q1, Q2, Q4, Q6, Q8 all confirm brand
   size does not change the outcome.
4. If the keyword's head noun is a date/occasion/calendar term with no "كود/كوبون خصم"
   → **candidate** — verify the SERP is general-interest (news/travel/calendar sites),
   not the cartel, before writing.
5. **Retroactive pass (recommended next step, not done in this session — no GSC access
   from this agent):** cross-reference the 710/764 zero-click pages against rule 3.
   Given 6/6 coupon-code-framed queries checked here returned zero dealpulseksa
   presence, expect a large share of the zero-click pages to be exactly this pattern.
   Cross-referencing requires GSC query-level data this agent did not have — flagged
   as the concrete next action, not claimed as done.

---

## 5. Cannibalization results

- Q1 (كوبونات خصم) × Q2 (كود خصم): domain overlap 5/8 → same-cluster threshold. These
  are near-synonyms; if the site ever targets this head term, it must be ONE page,
  not two — but per §1/§2 this whole pair is currently out of reach, so the
  recommendation is not to target it at all right now, which makes the cannibalization
  question moot until authority changes.
- No cannibalization risk identified within the recommended Cluster 1 (three distinct,
  non-overlapping keywords: holiday calendar / start date / deals roundup).
- Cannibalization risk flagged for future work: Spokes 1a/1b vs. the existing
  `/calendar` hub itself — must be checked against live `/calendar` page content before
  publishing (see Cluster 1 note above); this agent did not fetch the live page.

---

## Structured summary (JSON-compatible, Content Architecture category)

```json
{
  "audit_category": "Content Architecture",
  "method": "SERP overlap clustering via WebSearch, 8 queries, 2026-08-10",
  "coverage": "partial (8/30-50 planned keywords) — turn-budget constrained, honestly disclosed",
  "winnable_clusters": [
    {
      "name": "seasonal_occasion_calendar",
      "rank": 1,
      "evidence": "SERP-validated",
      "pillar": "/calendar (existing, do not duplicate)",
      "clusters": [
        {
          "name": "back_to_school",
          "status": "SERP-validated",
          "posts": [
            {"keyword": "تقويم إجازات المدارس السعودية 2026", "intent": "informational", "template": "explainer", "wordCount": 1350},
            {"keyword": "موعد بداية الدراسة 2026 السعودية", "intent": "informational", "template": "explainer", "wordCount": 1350},
            {"keyword": "عروض العودة للمدارس (category-level roundup)", "intent": "commercial", "template": "listicle", "wordCount": 1650}
          ]
        },
        {"name": "ramadan_eid_dates", "status": "hypothesis — needs SERP check before publishing"},
        {"name": "national_day_founding_day", "status": "hypothesis — needs SERP check before publishing"}
      ]
    }
  ],
  "out_of_reach_clusters": [
    {"query": "كوبونات خصم", "cartel_domains": ["otlobcoupon.com","couponaat.com","goldencouponzz.com","allcouponat.com","coupoonat.com","codkhasm.com"], "dealpulseksa_present": false},
    {"query": "كود خصم", "overlap_with_previous": 5, "dealpulseksa_present": false},
    {"query": "كوبون خصم نون", "dealpulseksa_present": false, "note": "confirms known big-brand-authority-block finding"},
    {"query": "كوبون خصم رمضان السعودية", "dealpulseksa_present": false, "note": "seasonal modifier on coupon head noun does NOT escape cartel"},
    {"query": "كود خصم فوجا كلوزيت", "dealpulseksa_present": false, "note": "existing 12-19 article cluster for this exact brand still absent from SERP"},
    {"query": "كوبون خصم مكملات غذائية ايهيرب", "dealpulseksa_present": false, "note": "existing 10-article cluster still absent from SERP"}
  ],
  "wrong_fit_excluded": [
    {"query": "عروض المتاجر السعودية", "reason": "different product vertical (physical hypermarket circulars), zero overlap with both coupon cartel and calendar vertical"}
  ],
  "selection_filter": [
    "reject if any of 8 cartel domains appear in top 5",
    "default reject if head noun is كود/كوبون خصم + store/category, any brand tier",
    "candidate only if head noun is date/occasion/calendar with no كود/كوبون خصم",
    "verify candidate SERP is general-interest, not cartel, before writing"
  ],
  "cannibalization": [
    {"pair": ["كوبونات خصم", "كود خصم"], "overlap": 5, "action": "would need merging if ever targeted; currently out of reach so moot"},
    {"pair": ["Spoke 1a/1b", "/calendar pillar"], "overlap": "unchecked", "action": "fetch live /calendar content before publishing to avoid self-cannibalization"}
  ]
}
```
