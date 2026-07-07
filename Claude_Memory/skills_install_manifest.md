---
name: Skills Install Manifest — 238 skills across 4 axes
description: What was actually installed on the "user" machine at ~/.claude/skills/ on 2026-07-07 — real live counts per repo, collisions resolved, hard walls preserved
type: project
originSessionId: b6ba939a-2469-4f6a-9833-5d2da06c5e04
---
**تحقّق حيّ 2026-07-07:** ٢٣٨ skill مثبَّت في `C:\Users\user\.claude\skills\` (flat layout: كل skill = مجلد فيه `SKILL.md`).

## المصادر الست (بالعدد الفعلي، لا الادّعاء التسويقي)

| المصدر | عدد SKILL.md | المحور | ملاحظة |
|---|---|---|---|
| `tjboudreaux/cc-thinking-skills` | ٣٩ | معرفة/تفكير | جميعها `thinking-*` (Bayesian, First-Principles, OODA, Pre-Mortem, Inversion, Steel-Manning, Fermi…) |
| `anthropics/skills` | ١٨ | تصميم + مستندات | ١٧ من README + template. يشمل brand-guidelines, canvas-design, frontend-design, algorithmic-art, mcp-builder |
| `plugin87/ux-ui-agent-skills` v2.4 | ١٧ | تصميم UX/UI | design-tokens, a11y-audit, apply-aesthetic, ١٣٨ نظام تصميم مضمَّن |
| `Owl-Listener/designer-skills` | ٩٦ | تصميم شامل | ٩ مجموعات: research/systems/UX-strategy/UI/interaction/prototyping/ops/toolkit/critique |
| `OpenClaudia/openclaudia-skills` | ٦٧ | تسويق | README ادّعى ٣٤ — الحيّ ٦٧. طبّقنا قاعدة العدّ الحيّ من [[feedback_mirror_audit]] |
| `aaaronmiller/create-viral-content` | ١ | إبداع محتوى | Hooks/headlines لـReddit/X/LinkedIn/TikTok |

## التصادمات المعالَجة

`ux-writing` و `content-strategy` كانا في مصدرين — الثانية أخذت لاحقة `-oc` (OpenClaudia).

## الملاحظات الإلزامية

- **الجهاز الآخر** (`C:\Users\PC\.claude\skills\`) عليه ١٧ تسويق من [[marketing_skills_toolkit]] فقط — لا تزامن تلقائي؛ إن أردنا نفس الحال هناك يعاد التركيب.
- كل ما ثُبّت **إنجليزي متحيّز غربي/SaaS**. المنهج ينتقل، المخرَج يُعاد سعودي/عربي.
- الحوائط الصلبة صامدة: [[seo_white_hat_only]] + [[bot_frozen_lock]] + [[feedback_no_db_writes_without_permission]].
- التنظيف: `C:\Users\user\.claude\skills-staging\` = 35MB يمكن حذفه بعد الاستقرار (`skills/` = 14MB).

## كيف أستدعيها

كل skill = ملف `SKILL.md` فيه YAML frontmatter (`name`, `description`). Claude يقرأها آلياً ويطابقها بالمهمة. لا استدعاء يدوي مطلوب — الوصف يوجّه المطابقة.
