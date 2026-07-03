---
name: regression-audit-own-changes-first
description: "When user says \"it was working before you changed it\", audit my own recent commits FIRST before blaming external config; avoid speculative code changes"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: a846dbe6-e8a1-40ed-82f7-d65eada0be73
---

When the user reports a regression — especially phrased as "it was working before" / "كان يشتغل قبل" / "كان يوصل بعد بس مدري وش سويت انت" — STOP and audit my OWN recent commits/diffs against the affected files FIRST. Do not theorize about external causes (tokens, permissions, platform-side config, expired credentials) until I've ruled out my own changes.

**Why:** In the 2026-05-28 social-broadcast session I twice blamed external Meta config when the real cause was my own code:
1. Facebook/Instagram/Threads broadcasts "broke" — I confidently blamed missing token permissions and wrong token type. Real cause: my own `f_webp` change in `image_specs.py` (Meta rejects WebP). Fixed by JPEG. See [[bug-fixes-log]] #8.
2. For Threads I then theorized "API access blocked = wrong token" and even made a *speculative* poll-before-publish change. The user's screenshots proved their Threads app was correctly configured and had been publishing. I reverted the speculative change to restore the proven-working original.

**How to apply:**
- On any "X stopped working" report: run `git log`/`git diff` on my recent changes touching X before proposing external fixes. My own diff is the cheapest, highest-yield suspect.
- Do NOT make preemptive/speculative code changes to a path the user says was working. Only change code with evidence of the actual current failure (real error text), not a theory about what *might* fail.
- This user pushes back firmly and is usually right when they say "it worked before" — treat that statement as a strong signal, not something to argue against. Verify with the code, then own the mistake plainly.
