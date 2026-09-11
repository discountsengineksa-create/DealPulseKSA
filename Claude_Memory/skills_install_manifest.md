---
name: skills-install-manifest
description: What is actually installed in ~/.claude/skills on each machine, the live per-repo counts, and the ux-ui payload trap that breaks 17 skills if you copy skill folders alone
metadata:
  type: project
---

**حيّ ٢٠٢٦-٠٨-١١ على جهاز `Users\PC`: ٢٩٦ skill + ٢٥ أمر** (بعد موجتين — انظر «موجة GitHub» أسفل). الموجة الأولى بلغت ٢٦١ skill (`(Get-ChildItem ~\.claude\skills -Directory).Count` = ٢٦١، و`SKILL.md` = ٢٦١ — واحد لواحد، لا تعشيش). قبلها كان ١٧ فقط.

**`C:\Users\user` ليس على هذا الجهاز** (`Get-ChildItem C:\Users` = Administrator, All Users, Default, Default User, PC, Public). لا نسخ مباشر بين الجهازين — **التركيب يُعاد استنساخاً من المصادر**.

## المصادر الستة — العدّ الحيّ ٢٠٢٦-٠٨-١١ (الـupstream انزاح عن ٢٠٢٦-٠٧-٠٧)

| المصدر | كان (٠٧-٠٧) | الحيّ (٠٨-١١) | المحور |
|---|---|---|---|
| `Owl-Listener/designer-skills` | ٩٦ | **١٠٧** | تصميم شامل (٩ مجموعات) |
| `OpenClaudia/openclaudia-skills` | ٦٧ | **٧٥** | تسويق |
| `tjboudreaux/cc-thinking-skills` | ٣٩ | **٢٨** | تفكير (انكمش) |
| `anthropics/skills` | ١٨ | **١٨** | تصميم + مستندات |
| `plugin87/ux-ui-agent-skills` | ١٧ | **١٧** | UX/UI |
| `aaaronmiller/create-viral-content` | ١ | **١** | محتوى |

**لا تنسخ الأرقام القديمة** — كل عدّ يُعاد بأمر عند التركيب.

## 🔴 الفخّ: مهارات ux-ui مؤشِّرات نحيفة لا حقائب مكتفية

`plugin87/ux-ui-agent-skills` يضع الـ١٧ في `.claude/skills/` بينما **المعرفة كلها في جذر الريبو**:
`design-systems/library/` (**١٣٨ نظام** — apple, linear-app, stripe, vercel, shadcn…)، `taste/`، `tokens/`، `scripts/`، `frameworks/`، `accessibility/`، `components/`، `workflows/`، `examples/`.

`apply-aesthetic/SKILL.md` = **١٧٨٨ بايت فقط** — كله إحالات لتلك المجلدات. **نسخ مجلد المهارة وحده = ١٧ مهارة مكسورة صامتة.**

**الحلّ المطبَّق:** الحمولة في `C:\Users\PC\.claude\skill-kits\ux-ui-agent-kit\` (٢٦٣ ملف / ٢.١MB) — **خارج `skills\` عمداً** كي لا يمسحها اللودر كمهارة — والـ١٧ متناً أُعيد توجيهها لمسارات مطلقة (٧١ إحالة تتحقّق بالوجود).

**ولا تُصحّح الـfrontmatter أبداً:** الاستبدال بالتعبير النمطي كتب المسار المطلق داخل `description:` لـ`figma-integration` و`governance` و`token-build` (`tokens/components` نصّ في جملة لا مسار)، فأفسد المطابقة حتى أُعيد الـfrontmatter حرفياً. **التصحيح للمتن فقط.**

## تسوية التصادمات

الـ١٧ القديمة من `coreyhaines31/marketingskills` ([[marketing_skills_toolkit]]) **تحتفظ بالاسم المجرّد** (غير معدَّلة: صفر حرف عربي، mtime ٢٠٢٦-٠٦-٢١)، والوافد المتصادم يأخذ لاحقة المصدر:
`content-strategy-ds` · `content-strategy-oc` · `ux-writing-ds` · `copy-editing-oc` · `copywriting-oc` · `product-marketing-oc` · `programmatic-seo-oc` · `seo-audit-oc` (٨ إعادات تسمية، والاسم في الـfrontmatter يُزامَن مع المجلد).

**مستبعَدان:** `claude-api` (يحجب المهارة المدمجة في الـharness) و`template` (قالب لا مهارة).

## موجة GitHub (٢٠٢٦-٠٨-١١) — ٣ مصادر إضافية، ٢٦١ → ٢٩٦

مسح GitHub Search API (لا `gh` على الجهاز) بحثاً عن أقوى مهارات واجهات:

| المصدر | ★ | المركَّب | لماذا |
|---|---|---|---|
| `nextlevelbuilder/ui-ux-pro-max-skill` | ١١٥٬٦٣٧ | **٧** | قاعدة محلية قابلة للبحث: ٨٤ ستايل / ١٩٢ بالِت / ٧٤ اقتران خطوط / ٩٨ قاعدة UX عبر ٢٢ ستاك + shadcn/Radix |
| `addyosmani/agent-skills` | ٨٦٬١٢٨ | **٢٤** | انضباط هندسي إنتاجي (`frontend-ui-engineering`, `performance-optimization`, `browser-testing-with-devtools`) — لا يغطّيه أيّ من الـ٢٦١ |
| `educlopez/ui-craft` | ٢٦١ | **٤ + ٢٥ أمراً** | نظام هندسة تصميم ضد «سلوب الـAI» |

**درس `ui-craft`:** الريبو يشحن ٢٩ verb-skill لـcodex/cursor/gemini، لكن **لـClaude يشحن ٤ مهارات + ٢٥ أمراً** في `commands/`. لا تركّب الـ٢٩ كمهارات — التركيب الصحيح: `cli/assets/claude/skills` → `~/.claude/skills\`، و`commands/` → `~/.claude/commands\` (`/polish`, `/critique`, `/finalize`, `/harden`…). **أول أوامر على هذا الجهاز — المجلد لم يكن موجوداً.**

**فخّ ثانٍ في التصحيح — مسار المستخدم ≠ حمولة الريبو:** رُحّل `docs/brand-guidelines.md` في ٣ مهارات (`brand`, `banner-design`, `design-system`) إلى مسار kit مطلق ميّت، بينما هو **ملف يُنشئه المستخدم في مشروعه**. القاعدة: صحّح فقط ما يوجد فعلاً في الريبو المصدر، وتحقّق بـ`Test-Path` بعد كل ترحيل.

**الحقائب الحيّة:** `~\.claude\skill-kits\ux-ui-agent-kit` (١٣٨ نظام) و`addyosmani-kit` (٧ checklists). **٩٦ إحالة مطلقة تتحقّق بالوجود، صفر مفقودة.**

**RTL: غير موجود على GitHub.** بحث `rtl arabic design system agent skill in:name,description` = **total=0**. لا مهارة عربية/RTL جاهزة في العالم — الفجوة تُسدّ بصناعة محلية.

## ملاحظات إلزامية

- **RTL/عربي شبه غائب**: ذكر RTL في **٤ ملفات فقط** (`localization-design` ١٠ مرات، `design-qa` ٣، `i18n` ١، `handoff-spec` ١). كل المهارات إنجليزية متحيّزة غربي/SaaS — **المنهج ينتقل، المخرَج يُعاد سعودي** ([[content_guardrails_playbook]]).
- الحوائط صامدة: [[seo_white_hat_only]] + [[feedback_no_db_writes_without_permission]] + [[bot_frozen_lock]].
- أربع مهارات اسمها في الـfrontmatter يخالف اسم المجلد upstream (`ahrefs-research`/ahrefs-python، `ai-image-gen`/generate-image، `brand-research`/brand-dev، `stock-images`/unsplash-image) — الـharness يعرضها **باسم المجلد**، فلا تنادِها باسم الـfrontmatter.
- الجهاز الآخر (`Users\user`) ما زال على تركيبته القديمة — **لا تزامن تلقائي**؛ أعِد نفس السكربت هناك إن أردت التطابق.
