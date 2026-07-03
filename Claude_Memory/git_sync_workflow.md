---
name: git-sync-workflow
description: "Cross-machine git sync — pull before work, commit+push after every completed change, ask which branch per task"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e7a3a201-94cf-4dda-9bb1-4bb3d4b5ec73
---

User works from **two machines** and treats GitHub (`origin`) as the source of truth for sync. Keep local and remote tight at all times.

**Rules:**
- After completing each logical code change, immediately `git add` (specific files) → commit with a clear message → push, so the other machine can pull right away. Push is authorized-by-default for completed work — no need to ask permission to push as such.
- **Ask which branch per task — do NOT assume.** `main` auto-deploys to Railway **production** on every push. `feat/store-analytics-bi` is the active WIP branch (store-analytics BI + opportunity engine) and is safe for work-in-progress. Confirm the target branch before pushing.
- At the **start** of a work session, `git fetch` / check divergence (and pull) before editing — never work on a stale copy.
- Always make real, meaningful commits (no junk "wip" messages). Never force-push to `main`.

**Why:** On 2026-05-28 the local folder (copied from the second machine) was **42 commits behind** `origin/main` — an old snapshot whose uncommitted work duplicated what was already on GitHub. Reconciling it was messy and risky. Tight pull-before / push-after discipline prevents recurrence. See [[setup-guide]].

**How to apply:** Treat completed changes as ready to push without asking permission, but DO ask which branch. Keep `main` clean/deployable; stage WIP on the feature branch and merge to `main` only when ready to ship.
