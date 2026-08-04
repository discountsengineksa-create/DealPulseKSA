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
`app/blog/*`، `app/sitemap.ts`، `app/llms.txt/route.ts`، `app/calendar/data.ts`،
`app/national-day/page.tsx`. **بأنماط glob فضفاضة (`app/category/**`) عاد الانهيار** —
احصر بأسماء ملفات صريحة. **احذف الملف بعد الفحص** حتى لا يُدفع.

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
- **`Invoke-RestMethod` يفسد العربية** — استعمل
  `[Text.Encoding]::UTF8.GetString((New-Object System.Net.WebClient).DownloadData($url))`
  ثم `ConvertFrom-Json`، وإلا رجعت الأسماء `Ø£Ø²ÙØ§Ø¡`.
- **أوامر PowerShell متعدّدة الأسطر تنهار** بـ`Internal Windows PowerShell error 80070005`
  أو `Starting the CLR failed` — اجمعها بسطر واحد بفواصل منقوطة.

## ٤) شكل ردّ `/admin/reindex-urls`

`results[].indexnow` **كائن مفاتيحه محرّكات** (`indexnow_bing/yandex/naver/seznam`) وكل
واحد فيه `.code` — **ليس** `.code` مسطّحاً. قراءته خطأً تعطي «0/39 فشل» كاذباً بينما الدفع
نجح. `results[].google.code` مسطّح فعلاً. يكمّل [[seo_bulk_reindex_ops]].
