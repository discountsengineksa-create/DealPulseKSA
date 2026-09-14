---
name: Maqalat — Verify Build Before Every Push
description: قبل أيّ push على maqalat شغّل `npm run build` محلياً؛ الـprebuild يفحص روابط MDX + Turbopack build كامل. المشكلة تكرّرت مرّتين من نفس النمط (٢٠٢٦-٠٩-١٣) — أهدرت ساعة كل مرّة
type: feedback
originSessionId: 245de921-acb1-4306-8d30-ea97bf4d3a03
---
## القاعدة

**قبل أيّ `git push` إلى `maqalat` (وليس أيّ ريبو آخر):**

```bash
cd C:\Users\user\Desktop\maqalat
npm run build   # ليس `npx next build` وحده
```

يجب أن ينتهي بـ `Compiled successfully` وتوليد الصفحات. أيّ خطأ = أوقف الدفع.

**Why**: Vercel يفشل بنفس السكربت (`npm run build`) الذي يُشغّل `prebuild → verify:links → next build`. جميع فشلي على Vercel في هذا الريبو كان بسبب فرق بين حالة قرصي المحلي وحالة الـcommit، وكان `npm run build` سيكشف الفرق قبل الدفع في أقلّ من دقيقة.

## نمطان تكرّرا (٢٠٢٦-٠٩-١٣)

### النمط الأول — Working tree stale
- `page.tsx` كان يظهر عليه `M` في git status (تعديل قديم من جلسة أخرى غير مكتمل الترحيل)
- قرأت النسخة الحاليّة (`toCardData`) وحرّرتها، لكن الـ`toCardData` كانت محذوفة من `lib/blog.ts` على الـremote (لم أفحص الفرق)
- Vercel: `Export toCardData doesn't exist` — فشل الـTurbopack build في ١٣ ثانية

### النمط الثاني — Untracked files referenced by tracked
- ٣٠ مقالاً MDX أنشأتها جلسة أخرى محلياً بلا `git add`
- ٦ منها كانت مُشار إليها من مقالات مدفوعة (`/sakani-housing-guide`، `/tamheer-programme-guide`، `/reef-agricultural-support-guide`)
- محلياً `verify-links: OK` لأن الملفات على القرص
- على Vercel: `verify-links: 11 BROKEN internal link(s)` — الـclone يجيب المتتبَّع فقط
- كل commits الجلسة (١٥+) فشلت في ٥ ثوانٍ

## How to apply

قبل الدفع لـmaqalat، **دائماً**:

1. **افحص المُهمل**: `git status --short | grep '^??' | grep 'content/articles/'` — لو فيه ملفات MDX بلا `git add`، انظر إن كانت مُشار إليها في مقالات ستُدفع. إن نعم = staje أو احذف الرابط
2. **افحص المُعدَّل بلا commit**: `git status --short | grep '^ M'` — لأيّ ملف تعديلاته لن تُدفع، افحص إن كان الكود المدفوع يعتمد على النسخة المعدّلة (يحدث حين تُحرّر ملفاً كان `M` مسبقاً)
3. **`npm run build`** كامل حتى الـstatic-page generation. الوقت التقديري:
   - `verify-links`: ثوانٍ
   - `next build compile`: ١٥-٢٠ ثانية
   - `static page gen`: ١-٢ دقيقة (٣٧٠+ صفحة)
   - **الإجمالي: ~٢-٣ دقائق**، والبديل: انتظار Vercel ٣-٥ دقائق + احتمال الفشل وإعادة الدورة
4. **ما يُدفع فقط**: `git diff origin/main --stat` قبل الـpush للتأكّد أنّ ما تراه هو ما ستراه Vercel

## المستثنى

- ريبو `Discounts_Engine` لا يحتاج هذا (main = Railway prod، بروتوكولها في `AGENT_PLAYBOOK.md §٤.٩`)
- ملفات الذاكرة فقط (`Claude_Memory/*.md`) لا تحتاج build
- تعديل `README.md` أو ملفات توثيق بحتة لا تحتاج

## اختصار عملي

لو الدفعة كبيرة (>٥ ملفات مصدر) أو تلمس أياً من: `content/articles/`، `components/`، `app/`، `lib/`، `mdx-components.tsx`، `next.config.ts` — **`npm run build` إلزامي**.
