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

## ١ب) ⚠️ صُحِّح ٢٠٢٦-٠٨-١٨: `next build` محلياً **ينتهي فعلاً**

`NODE_OPTIONS=--max-old-space-size=8192 npx next build` بعد `rm -rf .next` **أكمل بنجاح
(`EXIT=0`)** — كل المسارات مُصيَّرة، ٥٠+ صفحة متجر، و`sitemap.xml`/`robots.txt` مولَّدان.
شُغِّل في الخلفية لا في المقدّمة (يتجاوز مهلة الأمر الواحد).

⇒ **التحقّق المحلي الكامل متاح**، ولا حاجة للدفع للإنتاج «لنرى إن كان يبني». استُعمل فعلياً
للتحقّق من ترقية Next الأمنية (`15.5.19 ← 15.5.23`) قبل لمس `main`.
الفقرة أدناه محفوظة كسياق تاريخي — وكانت صحيحة وقتها (مهلة > ١٠ دقائق + قفل `.next/trace`).

### (النصّ السابق) `next build` محلياً لا ينتهي — Vercel هو بناء السجل

جُرّب ٢٠٢٦-٠٨-٠٨ بـ`NODE_OPTIONS=--max-old-space-size=8192`: **علّق >١٠ دقائق** بلا مخرَج
(١٬٧٤٧ صفحة prerender فوق `blog.ts` ٥٫٨MB)، وقبلها `EPERM` على `.next/trace` من قفل قائم.
⇒ **لا تَعِد بـ«تحقّقت بالبناء» في هذا الريبو.** الطبقتان اللتان تمسكان الخطأ فعلاً:
(أ) `tsc -p tsconfig.check.json` على الملفات المتغيّرة، (ب) ترجمة الوحدة المنطقية وحدها
بـ`npx tsc <file> --outDir <tmp> --module commonjs` ثم `require` وتشغيل دوالها الحقيقية
على البيانات الحقيقية (وصفة ٢ أدناه). ما بعدهما يُتحقَّق **حيّاً بـcurl بعد النشر**.

## ١د) 🔴 إشعار المهمة الخلفية **يكذب** على كود الخروج

شغّلتُ `next build` في الخلفية داخل أمر ملتفّ (`build > log; echo EXIT=$? >> log; tail`).
**الإشعار قال `exit code 0` بينما البناء فشل** (`EXIT=1` · `Failed to type check`) — لأن
الإشعار يقرأ كود **الأمر الملتفّ** لا كود البناء. لو صُدِّق لدُمج بناءٌ فاشل على الإنتاج.

⇒ **القاعدة: اقرأ `EXIT=` من داخل السجل، ولا تعتمد على حالة الإشعار إطلاقاً.**

## ١هـ) التحقّق الأقوى — شغّل خادم الإنتاج محلياً واختبره

بعد نجاح البناء، البناء وحده لا يثبت التشغيل:

```bash
PORT=3100 npx next start -p 3100 &     # جاهز خلال ~1.5 ثانية
# ثم اختبر ٩ أنواع مسارات: 200 + <title> + canonical + og:image + عدد H1
# و/sitemap.xml (عدد الروابط وlastmod) و/robots.txt (عدد User-agent)
```

استُعمل للتحقّق من هجرة Next 16 قبل لمس `main`: تسعة مسارات ٢٠٠ بعنوان وcanonical وog
وH1 واحد، و`sitemap` ١٬٧٢٨ رابطاً بـ`lastmod` على ١٬٦٠١ فقط، و`robots` بـ١٦ زاحفاً.
⚠️ أوقف الخادم بعدها: `Get-NetTCPConnection -LocalPort 3100 -State Listen`.

## ١و) هجرة Next 15 → 16 (٢٠٢٦-٠٨-١٨) — ما كسر وما لم يكسر

`next@16.3.1` + `postcss@8.5.26` ⇒ **`npm audit` صفر ثغرة** (كانت ٦ عالية)، و`sharp` خرج
من الشجرة كلياً.

- **الكاسر الوحيد:** `revalidateTag(tag)` صار `revalidateTag(tag, profile)` — الوسيط الثاني
  إلزامي. البروفايلات: `default · seconds · minutes · hours · days · weeks · max`.
  في `app/api/revalidate/route.ts` الصحيح `'max'` (خطّاف إبطال عند الطلب).
  و`updateTag` **ليست بديلاً** — محصورة بـServer Actions.
- **`eslint-config-next@16` يتطلّب `eslint>=9`** فتُرك على ١٥ عمداً: لا علاقة له بالثغرات،
  وترقيته هجرة flat-config منفصلة.
- **Next يعيد كتابة `tsconfig.json`**: `jsx: "preserve"` ← `"react-jsx"` (تشغيل React
  التلقائي) + `.next/dev/types` في `include`. تغيير متوقَّع لا يُعكَس.
- **لم يكسر:** لا `middleware`، لا `'use server'`، لا `next/legacy/image`، لا `next/amp`،
  و`await params` كان بالنمط الصحيح أصلاً في ٦ ملفات.

## ١ج) قياس Core Web Vitals بلا مفتاح — Lighthouse محلياً

`PageSpeed Insights API` يرجّع **429 بلا مفتاح**، و`CrUX API` يرجّع **403**. البديل الذي
يعمل فوراً (Chrome موجود على الجهاز):

```bash
export CHROME_PATH="C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
npx -y lighthouse "<url>" --only-categories=performance --form-factor=mobile \
  --throttling-method=simulate --output=json --output-path=<out.json> \
  --chrome-flags="--headless=new --no-sandbox --disable-gpu" --quiet
```

**قياس ٢٠٢٦-٠٨-٠٨ (جوال، محاكاة):** الرئيسية **perf 68 · LCP 3.39s · CLS 0.000 ·
TBT 703ms** · صفحة متجر (بيلاس) **perf 85 · LCP 2.63s · CLS 0.014 · TBT 335ms**.
⇒ **CLS ممتاز، LCP في النطاق البرتقالي (2.5–4s)، والعنق التفاعلية (TBT) على الرئيسية.**

**⚠️ الفرق الذي يُغفَل:** Lighthouse **بيانات مختبر (lab)**؛ جوجل يرتّب بـ**بيانات الميدان
(CrUX)** من مستخدمين حقيقيين، وهي **لا تتكوّن أصلاً دون حجم زيارات كافٍ**. بترافيكنا
(~١٢١ سعودي/شهر) الأرجح ألّا يكون لنا سجل CrUX — فتحسين CWV عندنا **استثمار تجربة مستخدم
لا رافعة ترتيب**. تحقّق من وجود سجل CrUX قبل صرف وقت عليه (يحتاج مفتاح API أو تقرير
«مؤشرات أداء الويب الأساسية» في GSC — وهو يقول «لا توجد بيانات كافية» حين لا يوجد سجل).

## ١ز) 🔴 قاعدة تنسيق صامتة تُسقط `FAQPage` بلا أي تحذير

مستخرِج الأسئلة في `app/blog/[slug]/page.tsx` (`extractFaq`) يشترط:
**السؤال فقرة مستقلّة** تطابق `^\*\*(.+)\*\*$`، **والجواب الفقرة التالية** — أي **سطر فارغ
بينهما**. كتابة السؤال في السطر الذي يعلو الجواب مباشرةً تدمجهما في فقرة واحدة فيفشل
التعبير النمطي **صامتاً**: صفر سؤال، وصفر `FAQPage`، **وبناء ناجح بلا خطأ ولا تحذير**.

وقع ٢٠٢٦-٠٨-١٨ في `gold-authenticity-hallmark-saudi` — والمقال كُتب أصلاً لقناة الاستشهاد
التي وقودها صيغة السؤال/الجواب، فكان سيُنشر بلا أثمن ما فيه.

**⇒ لا يكفي `EXIT=0`.** بعد أي مقال جديد تحقّق بالعدّ:
```bash
find .next -path "*<slug>*" -name "*.html" | while read f; do
  echo "FAQPage: $(grep -c FAQPage "$f") | Question: $(grep -o '"Question"' "$f" | wc -l)"; done
```
أو حيّاً بعد النشر: اسحب الصفحة وابحث عن `FAQPage` و`"Question"` وعُدّهما.
**القاعدة الأعمّ: افحص الـHTML المُصيَّر بعد كل نشر محتوى — الصمت ليس نجاحاً.**

## ٢) اختبر العناوين بالدوال الحقيقية لا بإعادة كتابتها

قبل تغيير عنوان مُولَّد لصفحات كثيرة: ترجم `lib/seo/metadata.ts` بـ
`npx tsc lib/seo/metadata.ts --outDir <tmp> --module commonjs --target es2020 --rootDir lib`
ثم `require` الناتج ومرّر **الوسوم الحقيقية من API الإنتاج**
(`/api/v1/coupons/categories`) على `clampTitle`/`clampDescription`.
افحص: هل قُصّ العنوان الخام؟ هل خرج الوصف عن [110, 158]؟
(٣٨ وسماً: العناوين ٤٣–٥٧، الأوصاف ١١٥–١٤٣، صفر قصّ.)

## ٢ب) معايرة حركة CSS: جمّدها عند ذروتها وصوّرها

شحنتُ وميضاً على خط التقطيع **لم يُرَ إطلاقاً** (٢٠٢٦-٠٨-١١): كان يضيء
`border-top-color` على خيط `2px dashed` — نصف مساحته فراغ — بذروة ١٢٨ms.
التقدير بالعين على الكود لا يكشف هذا؛ **الحركة تُقاس بإطار مجمّد**:

```css
/* الذروة عند 20% من 560ms = 112ms */
.frozen .x, .frozen .x::after {
  animation-delay: -112ms !important;
  animation-play-state: paused !important;
}
```

ثم صفحة فيها ثلاث نسخ جنباً إلى جنب (بلا حركة / الحالية / أقوى) ولقطة headless واحدة.
حسمت أن `0.60α/14px` غير مرئية و`0.95α/22px` واضحة.

**⚠️ ولا تستخرج CSS بتعبير نمطي للاختبار** — تعبيري بتر `@keyframes` ذا الثلاث مراحل
فأظهر النسختين متطابقتين وكاد يقنعني أن المشكلة في مكان آخر. اكتب قواعد الاختبار صراحةً.

**وتحقّق من `position: relative`** على أب أي `::after` مطلق — الهالة كانت تُحسب من
البطاقة كلها لا من الخط.

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
