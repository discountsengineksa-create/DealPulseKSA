---
name: blog.ts String Hazards — Backticks AND Apostrophes
description: في dealpulseksa-web/lib/blog.ts، body strings تكسر بسهولة من ``` (داخل template literals) أو ' غير محمي (داخل single-quoted strings). افحص قبل push.
type: feedback
originSessionId: 55f414d0-ba1d-432d-bde6-f036ad762470
---
في ملف `dealpulseksa-web/lib/blog.ts`، حقل `body:` لكل مقال إما **template literal** (`` `...` ``) أو **single-quoted string** (`'...'`). كلاهما له فخّ مختلف يكسر SWC parser ويوقف كل Vercel builds التالية.

## الفخّان

### 1) Triple Backticks في Template Literals
لا تكتب ``` (code fence) داخل body template literal — يفسّرها SWC كنهاية template literal مبكرة.

### 2) Apostrophe غير محمي في Single-Quoted Strings
لا تكتب `'` (مثل `Pandora's`, `Land Cruiser's`, `don't`, `it's`) داخل single-quoted body — اكتبها `\'` بدلاً.

## Why
**حادثة 1 (2026-06-27)**: مقال «حماية الشمس» احتوى ``` داخل template literal → 43 مقال علي اكسبرس عالقة → GSC sitemap بقي 256 صفحة. المستخدم اكتشف المشكلة من Vercel Build Logs قبل تشخيصي الأول الخطأ (out-of-memory).

**حادثة 2 (2026-06-28)**: مقال «أنظمة الأمان» احتوى `Pandora's Pro Version` في single-quoted body → 17 commit (100+ مقال) عالقة 8+ ساعات → كل Vercel deployments فشلت → live site بقي 46 مقال علي اكسبرس من أصل 150 في git. المستخدم رفع تنبيه «كل الشغل مضروب» قبل تشخيصي.

## How to apply
**قبل أي commit يضيف/يعدّل blog.ts**:
1. `grep -n '\`\`\`' lib/blog.ts` يجب أن يعود فارغاً.
2. `grep -E "body: '[^\\\\]*[a-zA-Z]'s [a-zA-Z]" lib/blog.ts` يجب أن يعود فارغاً (يكشف `word's word`).
3. `grep -E "body: '[^\\\\]*'(t|re|ve|ll|d|m) " lib/blog.ts` يكشف contractions غير محمية.

**عند الكتابة الجديدة**:
- في single-quoted body: استبدل كل `'` بـ `\'` فوراً.
- لو محتوى المقال فيه نقاط كثيرة، استخدم template literal `` ` `` بدلاً من `'` — أأمن.
- لكن تذكّر: template literal يكسر من ``` وsingle-quoted يكسر من `'` — لا حلّ آمن 100%.

**عند فشل Vercel deployment**:
- افتح Build Logs مباشرة. لا تفترض السبب.
- ابحث عن السطر بـ `Expected ',', got '...'` — يدلّك على الخطأ.
- الإصلاح في 5 دقائق، التأخير في التشخيص ضاع 8 ساعات.
