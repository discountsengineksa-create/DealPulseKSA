---
name: bot-frozen-no-changes-without-explicit-approval
description: The Telegram bot is locked; never modify bot files unless the user explicitly asks in-conversation
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c68f1e02-f8e3-449a-b56a-5cb4bf29185a
---

🔒 **LOCKED as of 2026-06-10.** The user explicitly froze the Telegram bot: «احفظ وثبت كل شي الان خاص بالبوت ولا يتغير ابدا الا بعد ما تقول لي وحط الشرط هذا».

**Frozen scope (do NOT edit these without explicit per-change approval):**
- `deal_pulse_bot.py`
- `bot_app.py`

Locked baseline = git tag **`bot-locked-2026-06-10`** (commit e37eeb6 on `main`).

**The condition (governs every session):**
- Do NOT modify, refactor, "improve," clean up, or optimize the bot files — for ANY reason — unless the user explicitly asks for that specific change in the current conversation.
- This overrides default helpfulness: even if I spot a bug, dead code, or an easy win, I **report it and WAIT** for an explicit go-ahead. I do not touch the files first.
- "Apply the cheap wins / fix everything" style blanket approvals do NOT carry over to future sessions — each bot change needs a fresh explicit request.
- Mini-web (`miniapp.html`) and the web repo (`dealpulseksa-web`) are NOT covered by this lock unless the user says so — confirm scope if a request is ambiguous.

**How to apply:** before any Edit/Write to a frozen file, confirm the user explicitly requested it. If not, stop and ask. Related work principle: [[feedback-no-dead-code]].
