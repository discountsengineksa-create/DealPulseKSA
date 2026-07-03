---
name: no-dead-code-or-premature-optimization
description: "User rejects dead/fake/speculative code; only ship real, wired, justified changes"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c68f1e02-f8e3-449a-b56a-5cb4bf29185a
---

User (2026-06-10, during the bot load-capacity work): «يا بروفسور ما ابي اكواد ميته و وهميه» — do NOT add dead code, fake/placeholder code, or speculative abstractions.

**Why:** matches their broader zero-fakery / enterprise due-diligence mandate ([[analysis_rebuild_strategy]]). Every line must be real, fully wired, and justified by an actual bottleneck — not "might need it later" scaffolding.

**How to apply:**
- Before adding an abstraction (executor, queue, layer), confirm it raises a REAL ceiling. Example that was correctly REMOVED: I added a `ThreadPoolExecutor` to defer analytics writes off the hot path, but the true bottleneck is Telegram's ~30 msg/s cap, not the DB — so the async layer added complexity without raising the ceiling = premature optimization. I deleted it and kept only the simple real wins (more workers, bigger queue, pool size, gating backfill).
- If you add a helper/function, wire it everywhere it belongs in the same change — never leave a half-used symbol.
- Prefer the smallest real change that moves the actual metric. Profile/identify the binding constraint first.
- Don't keep code paths that never execute; make conditional code genuinely reachable (e.g. `RUN_BACKFILL=1` one-time job is fine — it's reachable and purposeful).
