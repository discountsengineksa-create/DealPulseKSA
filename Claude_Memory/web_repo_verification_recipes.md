---
name: web_repo_verification_recipes
description: وصفات تحقّق مثبتة في dealpulseksa-web — tsconfig ضيّق يتجاوز OOM، تمرير الوسوم الحقيقية على clampTitle، ومطبّ العربية داخل .ps1
metadata: 
  node_type: memory
  type: reference
  originSessionId: 0d2aefa2-1820-4232-9c2b-90aa95b76d39
  modified: 2026-08-04T18:17:20.891Z
---

## ١) تجاوز الـOOM بـtsconfig ضيّق (بديل عملي أسرع من TS parser API)

`npx tsc --noEmit` على الريبو كامل **يـOOM حتى بـ8GB** بسبب `lib/blog.ts` (~5.8MB) —
سقف موثّق في [[web_blog_monolith_oom_and_client_prop_serialization]].

**الوصفة:** `tsconfig.check.json` يرث الأصل ويحصر `include` في **الملفات المتغيّرة فقط**:

```json
{ "extends": "./tsconfig.json",
  "compilerOptions": { "incremental": false },
  "include": ["next-env.d.ts", "app/category/[slug]/page.tsx", "..."],
  "exclude": ["node_modules"] }
```

يفحص الملف **ورسمه الاستيرادي كاملاً** (translations, lang, api, seo/*) في ثوانٍ.
**شرطه الوحيد:** ألا يستورد أيٌّ منها `lib/blog.ts` — تحقّق بـgrep أولاً؛ المستوردون هم
`app/blog/*`، `app/sitemap.ts`، `app/llms.txt/route.ts`.
**بأنماط glob فضفاضة (`app/category/**`) عاد الانهيار** — احصر بأسماء ملفات صريحة.
**احذف الملف بعد الفحص** حتى لا يُدفع.

**⚠️ تصحيح ٢٠٢٦-٠٨-٠٨:** كانت هذه الفقرة تعدّ `app/calendar/data.ts` و
`app/national-day/page.tsx` من مستوردي `lib/blog.ts` — **غلط**. `data.ts` فيها
**صفر استيرادات** أصلاً، والمطابقة كانت على **تعليق** يذكر الاسم لا على `import`.
(لأجل هذا صار استيرادها في اللياوت السِتوايد آمناً.) **القاعدة: `grep 'lib/blog'` وحده
يمسك التعليقات — احصر بـ`grep -nE "^\s*import.*lib/blog"` قبل أن تسمّي ملفاً مستورِداً.**

## ١ب) `next build` محلياً **لا ينتهي** — Vercel هو بناء السجل

جُرّب ٢٠٢٦-٠٨-٠٨ بـ`NODE_OPTIONS=--max-old-space-size=8192`: **علّق >١٠ دقائق** بلا مخرَج
(١٬٧٤٧ صفحة prerender فوق `blog.ts` ٥٫٨MB)، وقبلها `EPERM` على `.next/trace` من قفل قائم.
⇒ **لا تَعِد بـ«تحقّقت بالبناء» في هذا الريبو.** الطبقتان اللتان تمسكان الخطأ فعلاً:
(أ) `tsc -p tsconfig.check.json` على الملفات المتغيّرة، (ب) ترجمة الوحدة المنطقية وحدها
بـ`npx tsc <file> --outDir <tmp> --module commonjs` ثم `require` وتشغيل دوالها الحقيقية
على البيانات الحقيقية (وصفة ٢ أدناه). ما بعدهما يُتحقَّق **حيّاً بـcurl بعد النشر**.

## ٢) اختبر العناوين بالدوال الحقيقية لا بإعادة كتابتها

قبل تغيير عنوان مُولَّد لصفحات كثيرة: ترجم `lib/seo/metadata.ts` بـ
`npx tsc lib/seo/metadata.ts --outDir <tmp> --module commonjs --target es2020 --rootDir lib`
ثم `require` الناتج ومرّر **الوسوم الحقيقية من API الإنتاج**
(`/api/v1/coupons/categories`) على `clampTitle`/`clampDescription`.
افحص: هل قُصّ العنوان الخام؟ هل خرج الوصف عن [110, 158]؟
(٣٨ وسماً: العناوين ٤٣–٥٧، الأوصاف ١١٥–١٤٣، صفر قصّ.)

## ٣) مطبّات أدوات (Windows / PowerShell 5.1)

- **لا تكتب عربية داخل ملف `.ps1`** — أداة Write تكتب UTF-8 بلا BOM، و5.1 يقرأه ANSI
  فينكسر التحليل (`The string is missing the terminator`). أبقِ رسائل السكربت إنجليزية،
  والعربية في ملفات بيانات/رسائل commit فقط. يكمّل مطبّ here-string في
  [[seasonal_school_traffic_bridge]] (استخدم `git commit -F <ملف>`).
- **⚠️ `certificate has expired` من بايثون على `api.dealpulseksa.com` = **مخزن شهادات محلي
  بايت، لا عطل إنتاج**. حزمة `certifi` هنا من ٢٠٢٥-٠٣ فلا تعرف جذر Let's Encrypt الأحدث
  (`CN=YE2`). الشهادة الحقيقية سليمة (تحقّق: `openssl s_client -connect … | openssl x509
  -noout -dates`) و`curl` يمرّ 200. **استعمل `curl` لنداءات API الإنتاج، ولا تُنذر بعطل TLS
  قبل قراءة تواريخ الشهادة فعلياً.**
- **`Invoke-RestMethod` يفسد العربية** — استعمل
  `[Text.Encoding]::UTF8.GetString((New-Object System.Net.WebClient).DownloadData($url))`
  ثم `ConvertFrom-Json`، وإلا رجعت الأسماء `Ø£Ø²ÙØ§Ø¡`.
- **أوامر PowerShell متعدّدة الأسطر تنهار** بـ`Internal Windows PowerShell error 80070005`
  أو `Starting the CLR failed` — اجمعها بسطر واحد بفواصل منقوطة.

## ٤) شكل ردّ `/admin/reindex-urls`

`results[].indexnow` **كائن مفاتيحه محرّكات** (`indexnow_bing/yandex/naver/seznam`) وكل
واحد فيه `.code` — **ليس** `.code` مسطّحاً. قراءته خطأً تعطي «0/39 فشل» كاذباً بينما الدفع
نجح. `results[].google.code` مسطّح فعلاً. يكمّل [[seo_bulk_reindex_ops]].
