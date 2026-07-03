---
name: memory_sync_junction
description: كيف تتزامن ذاكرة Claude بين الجهازين — junction على مجلد Claude_Memory داخل الريبو
metadata: 
  node_type: memory
  type: project
  originSessionId: bba26cc8-725d-471c-9780-36804298b013
---

ذاكرة Claude تُخزَّن مرّة واحدة فقط داخل الريبو بمجلد `Claude_Memory/` (على جذر DealPulseKSA repo)، ومجلد الذاكرة الحيّة على كل جهاز مجرّد **junction** يشير إليه — فلا يوجد تكرار ولا نسخ يدوي.

**السبب:** الجهازان (PC و user) كانا يبنيان ذاكرتين محليّتين منفصلتين فتفرّعتا (47 مقابل 19) والجهاز الثاني بان "أغبى" لأنه بسياق أقل. وحّدناهما إلى 68 ملف ثم ربطناهما بالريبو عبر junction (2026-07-03) لمنع التفرّع للأبد.

**كيف تطبّق/تصلّح:**
- الوصلة على كل جهاز: `~/.claude/projects/c--Users-<user>-Desktop-Discounts-Engine/memory`  →  `<repo>/Claude_Memory`
- الأمر (PowerShell، لا يحتاج أدمن — junction وليس symlink): `New-Item -ItemType Junction -Path $link -Target $target`
- المزامنة تلقائية عبر عادة الـ git: `pull` أول الجلسة + `push` بعد الشغل (انظر [[git_sync_workflow]] و [[feedback_always_push]]). أي تعديل ذاكرة يظهر في `git status` مع الكود.
- `.gitignore` كان يتجاهل `Claude_Memory/` (بقايا محاولة سابقة) — أُزيل التجاهل ليُتتبَّع؛ `Transfer_Package/` ما زال متجاهلاً.
- الريبو خاص (private) فالاستراتيجية والتفضيلات داخله بأمان.
