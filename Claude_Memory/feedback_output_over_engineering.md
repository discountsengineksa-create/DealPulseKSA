---
name: judge-by-output-not-engineering-effort
description: "User rates work by the final deliverable's quality, not by how hard the plumbing was — surface a tool's quality ceiling honestly BEFORE building on it"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: dcbefbd3-090a-4777-a5f7-85c964c50ca9
---

The user judges work purely by the **quality of the final output**, never by how much engineering went into making it run. A technically impressive fix (e.g. a 5-layer dependency install battle) counts as **0/100** if the thing it powers produces a weak result.

**Why:** On the local XTTS TTS engine (2026-07-06) I got a genuinely hard install working and demoed it — the user's verdict was "0 من 100، ما يستاهل التعب" because the *voice* sounded robotic, not the «فخم» / طبق-الأصل result he pictured. All the plumbing wins were worthless to him.

**How to apply:**
- When a chosen tool/engine has a **known quality ceiling below what the user wants**, say so loudly and FIRST — before investing effort making it run. Don't polish a fundamentally-limited option and let them discover the ceiling at the end.
- Lead with the honest state-of-the-art and the real (even paid) path to the actual goal; treat "free/local/no-API" as a *means* the user may trade away once he sees it caps the outcome, not an immovable constraint.
- Don't defend finished work with a list of accomplishments when he's unhappy with the result — accept the verdict, diagnose the ceiling, redirect to what actually hits the bar.
- Aligns with [[feedback_senior_engineer]] (no philosophy, blunt expertise) and [[feedback_no_philosophy]]. See [[tts_engine_xtts_v2]] for the case that produced this.
