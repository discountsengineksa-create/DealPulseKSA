---
name: Always Push, Never Leave Work Local
description: User works across multiple devices — every commit must be pushed; never leave uncommitted/unpushed work behind
type: feedback
originSessionId: e8c93de7-985e-4921-8bd5-22b03fb17c33
---
كل تغيير لازم ينتهي بـ `git add` + `git commit` + `git push`. ما يصير نخلّي تعديلات في working tree، ولا commits محلية بدون دفع، ولا stash.

**Why:** المستخدم يشتغل من أجهزة متعددة (الجهاز الأول والثاني على الأقل). أي شي يبقى محلي = ضياع للشغل أو merge conflicts ضخمة لما يفتح الريبو من جهاز ثاني. صار فعلياً: نسيان دفع 6+ commits من الجهاز الأول سبب divergence و conflict كبير اضطر يحل يدوياً.

**How to apply:**
- بعد أي edit/commit أنا أسوّيه: ذكّر المستخدم بـ push أو اعرض تنفيذه (لا تنفّذ push بدون إذن، لأنه أكشن مرئي للغير).
- لو لقيت commits محلية ما اتدفعت في بداية الجلسة: نبّه فوراً.
- لو في working tree changes غير محفوظة قبل ما نشتغل على شي جديد: نبّه قبل ما نكمل.
- لا تستخدم `git stash` كحل سريع — تخفي الشغل عن الجهاز الثاني.
- قبل ما تبدأ شغل جديد في جلسة، تأكد `git pull` أول (الجهاز الثاني ممكن دفع شي).
