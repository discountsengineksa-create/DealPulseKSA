---
name: reconcile-web-repo-separately
description: The web frontend is a SEPARATE git repo from Discounts_Engine and can be behind its own remote even after pulling the main repo — fetch/check it at session start
metadata: 
  node_type: memory
  type: project
  originSessionId: 269657c1-3da1-4d4b-94c7-88a5f072c9e7
---

The Next.js website lives in its **own git repo** at `C:\Users\PC\Desktop\dealpulseksa-web` (remote: `github.com/discountsengineksa-create/dealpulseksa-web`), separate from `Discounts_Engine` (remote: `DealPulseKSA`). The two-machine workflow means **the web repo can be many commits behind its remote even when Discounts_Engine is up to date** — pulling one does NOT pull the other.

**Why:** In one session I built `StoresBrowser` + my own `lib/trend.tsx` on a stale web base; on push it conflicted because the other machine had already shipped a full web trend system (`lib/trend-helpers.ts`, `TrendCard`, `HomeTrendSection`, rebuilt `/trending`, `getDailyTrend`/`getWeeklyTrend` in api.ts, `StoresListing`). I had to reset to origin/main and re-apply on top, reusing their infra instead of duplicating.

**How to apply:** Before editing the web project, run `git -C <web> fetch && git -C <web> status` and pull if behind. Before building anything trend/stores-related, check what already exists on the web side (api.ts trend fns, components/). Reuse, don't duplicate. Note: as of 2026-06, the web `StoreCard` badge now uses the new daily/weekly trend via a `TrendProvider` (`lib/trend.tsx`) I added — not the legacy `is_trending` flag. See [[git-sync-workflow]] and [[feedback-regression-audit]].
