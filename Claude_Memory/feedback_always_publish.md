---
name: feedback-always-publish
description: "User wants me to always commit + push (publish) automatically when a task is finished, without asking"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 269657c1-3da1-4d4b-94c7-88a5f072c9e7
---

When I finish a coding task, **commit and push automatically** to deploy — the user said «دائما انشر اذا خلصت» (always publish when done). Don't wait to ask permission to publish.

**Why:** `main` deploys straight to prod (Railway for API/dashboard/miniapp-repo, Vercel for the web repo). The user treats "done" as "deployed", and finds the extra confirmation step friction.

**How to apply:** After changes are verified (typecheck/build pass), commit with a clear message and `git push origin main` for each affected repo. Still ask which branch only if it's genuinely ambiguous; default is `main`. See [[git-sync-workflow]] and [[reconcile-web-repo-separately]].
