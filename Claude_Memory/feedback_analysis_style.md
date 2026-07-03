---
name: feedback-analysis-style
description: "How the user wants analytics built — comparative decision-driving tables across ALL stores, working code over decorative talk; what to drop"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 981b8ddc-71cf-40ba-bb27-30bdfc73c992
---

When building the analysis/BI pages, the user wants **comparative, decision-driving output across ALL entities (all stores), not single-example drill-downs**, and **working code/actions, not decorative writeups**.

**Why:** He said literally «مابي كلام ملمع حراري وخرابيط ابي افعال واكواد تنفعني في عملي» and «ما يهمني المستخدمون الفريدون ولا متوسط نسخه». He gives one example (e.g. a Salla per-coupon screenshot) but warns: «مابي اقولك شي او اعطيك امثله ويتمسك في شي ويروح فكرك الابداعي» — don't fixate on the literal example, grasp the underlying need.

**The decisions he actually wants the analytics to drive:**
- Which store is TOP (نسخ/نقرات/بحث) → focus on it.
- Which store is LOWEST → drop it / stop wasting effort.
- Who to give الترند, who to pull الترند from.
- Most vs least searched store; most vs least copied (with exact counts).
- All stores at once: copies per store, clicks at minute/hour/up-to-last-moment granularity or per his date filter, and FROM WHOM (which users copied), and from WHICH source (bot vs web).

**Quality bar — finish each page before moving on:** He said «انا ماراح اطلع من صفحة الا وانا مقفلها بشكل صحيح بما يفيدني ويفيد العميل والشركات المعلنه والشركات عند البيع». So fully close/perfect the current analysis page (real data, no gaps, no fakery) before starting the next. Every page must serve 4 audiences at once: (1) him/ops, (2) the end customer, (3) advertiser brands, (4) acquirers at sale. Don't move to the next page until he confirms the current one is done right.

**How to apply:** Lead with a ranked comparison table + a rule-based «التوصية» column (رشّح للترند / اسحب الترند / مرشّح للإيقاف / مستقر). Skip vanity metrics (unique users, avg-per-user), skip heatmaps/sunbursts/«strange ideas»/far-field analogies unless he asks. Keep prose minimal; deliver runnable code that fits existing helpers. Identity coverage for Telegram is COMPLETE (usernames + telegram fingerprint for everyone) — do NOT hedge it. See [[analysis-rebuild-strategy]] and [[store-analytics-bi]].
