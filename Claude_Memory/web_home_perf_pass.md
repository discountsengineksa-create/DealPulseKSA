---
name: web_home_perf_pass
description: جولة أداء الرئيسية ٢٠٢٦-٠٩-٠٧ — TBT ٢٩٠٠→٢٠ms بـgtag lazyOnload، تقليم النبذة، content-visibility للأقسام تحت الطيّة؛ السقف الباقي LCP وهو ليس رافعة ترتيب
metadata:
  type: project
---

**السياق:** لوحة «أداء SEO» في الداشبورد أظهرت الأداء ٨٤ متذبذباً (٥١↔٩٦ في `seo_perf_snapshots`).
شُخِّص: ٩٠٪ تشتّت مختبر Lighthouse على صفحة ثقيلة JS + سقف نزل ~٩ نقاط منذ ١٨–٢٠ أغسطس
(GA4 + Next 16 + إعادة ضبط الألوان). وانحداران حقيقيان مؤرَّخان (best-practices ١٠٠→٩٢،
accessibility ١٠٠→٩٦) عولجا — انظر [[web_ga4_install]] و[[security_hardening]].

## ما نُفِّذ (web `1805c7a` + `243dd29`)

| التغيير | الأثر المقيس |
|---|---|
| `gtag.js` من `afterInteractive` → **`lazyOnload`** (`GoogleAnalytics.tsx`) | **TBT ٢٩٠٠ms → ٢٠ms** على PSI؛ اختفى التذبذب (الرقم كان يقفز لأن تنفيذ gtag ١٧٠KB يزاحم ترطيب React عشوائياً) |
| **`trimForHome()`** في `app/page.tsx` — تصفير `store_bio`/`store_bio_en` خادِمياً قبل تمرير الكتالوج لـ`HomeContent` (`'use client'`) | `index.html` المُصيَّر **٤١٠KB → ٣٥٥KB**؛ صفر تغيير بصري (البطاقات كلها `variant="compact"`، النبذة بند `detailed` فقط) |
| **`.cv-section`** (`content-visibility: auto; contain-intrinsic-size: auto 640px`) على كل قسم من الترند نزولاً في `HomeContent.tsx` | Style & Layout **~١١s → ١٫٦s**، إجمالي الخيط الرئيسي **١٨٫٤s → ٦٫٣s**، Speed Index **٥٫٩s → ٢٫٤s**، **CLS بقي ٠** (بناء محلي، jوال، simulate 4x) |

**لماذا `.cv-section` هو الرافعة:** الرئيسية ترسم ~٢٠ بطاقة `.glass`، كلٌّ بـ`backdrop-filter:
blur(28px) saturate(180%)` — أغلى خاصية CSS على الجوال (`--dpk-blur: 28px` في `globals.css`،
يضبطه الداشبورد عبر `SiteThemeBackground`). لم تُلمس القيمة — قرار هوية. `content-visibility`
يؤجّل تخطيط/رسم القسم (بما فيه الـblur) حتى يقترب من نافذة العرض. **لا يُطبَّق على أول ٣ أقسام**
(`StoreStories` · `FeaturedStores` · `Hero`) — فوق الطيّة. المحتوى يبقى في DOM ويُفهرَس.

## السقف الباقي — LCP، وهو **ليس رافعة ترتيب لنا**

بعد الجولة: PSI perf ~٨٧ ثابت، **LCP ٣٫٩s** هو ما يمسك الرقم (CSS يحجب التصيير ~١٢٠ms +
تحميل الخطوط + عنصر الـHero النصّي). رفعه لـ٩٠+ يحتاج إمّا:
- **تحويل `HomeContent` من `'use client'` إلى شجرة Server Components** (Hero/البطاقات تستخدم
  hooks للمفضلة/النسخ — refactor حقيقي، مشروع لا جولة).
- micro-opts على تحميل الخطوط/CSS الحرج — عائد ٢٠٠–٥٠٠ms، خطر انحدار بصري.

**والحقيقة التي توقف الصرف:** بترافيكنا (~٥٤٦ سعودي/٣٠ي) **لا سجل CrUX** غالباً، وجوجل يرتّب
ببيانات الميدان لا المختبر ⇒ رقم Lighthouse **تجربة مستخدم لا ترتيب**. تحقّق من وجود سجل CrUX
(تقرير «مؤشرات الويب الأساسية» في GSC) قبل صرف وقت على LCP. يكمّل [[web_repo_verification_recipes]] §١ج.

## أداة الداشبورد

`dashboard.py` صفحة «أداء SEO» (`bdaa218`): PSI انتقل لـLighthouse 12 فصارت «الفرص» فحوص
`*-insight` بنوع `details` مختلف — الفلتر القديم (`type=="opportunity"`) أظهر بنداً واحداً بينما
الحقيقة ٦. الفلتر الآن يقبل `-insight` و«Est …» ويزيل التكرار بالعنوان.
