---
name: Maqalat Content Audit 2026-09-02
description: تدقيق شامل للمقالات العشر + سجل الإصلاح المُنفَّذ في نفس اليوم (E-E-A-T + P0 salary + methodology page)
type: project
originSessionId: b5fb45a3-ddd1-4608-b0ca-0c93163e7e4e
---

## ✅ حالة الإصلاح (2026-09-02 مساءً)

**تم شحنه لـ Vercel (commits: `d5e07f5` + `140ad5d` على maqalatorg/maqalat)**:
- [x] **P0 نظام الرواتب**: `lib/salaries.ts` + `lib/hijri.ts` + `SalaryCalendar.tsx` + المقال — راتب حكومي ٢٧ **ميلادي** (كان هجري خاطئ)، متقاعدون ١ ميلادي (كان ٢٧ هجري)، سبت→أحد بعده (كان خميس قبله). تحقّق إنتاجي: 3× "٢٧ ميلادي" + 0× "هجري" ✓
- [x] **Publisher schema قوي**: `lib/seo.ts` — Organization بـ publishingPrinciples/correctionsPolicy/diversityPolicy/knowsAbout؛ helpers جديدة: `breadcrumbJsonLd()` + `howToJsonLd()`. تحقّق: زكاة يعرض `Article` + `BreadcrumbList` + `FAQPage` + `HowTo` ✓
- [x] **صفحة /methodology**: AR + EN، ٧ أقسام (اختيار الموضوع، تسلسل المصادر، لا نشره، شفافية AI، YMYL، التصحيحات، الاستقلالية). فوتر + reserved slug + sitemap. تحقّق: `200` على AR و EN ✓
- [x] **Mayo Clinic استُبدل** بـ Harvard Nutrition Source + ACOG + CDC عبر ٤ مقالات صحية (AR+EN). صفر ذكر `mayoclinic` في المحتوى.
- [x] **الافتتاحيات الـAI-typical** أُعيد كتابتها (تقويم، BMI، حمل، دورة) بمفارقات/أرقام/توطين محلي بدل "يحتاج المستخدم"/"من أهم".
- [x] **inline citations** استبدلت قوائم مصادر النهاية في المقالات الأربع.
- [x] **cluster health** فُعّل ونُقلت ٤ مقالات صحية إليه (AR+EN).
- [x] **الكاتب** وُحّد إلى "مقالات" (publisher-driven E-E-A-T بلا كاتب فردي مزيّف) — قرار المالك: لا كاتب حقيقي.
- [x] **whoBody في About** أُعيد صياغته بشفافية: "منصّة نشر رقمية بلا كاتب فردي مزيّف" مع رابط للـmethodology.
- [x] **descriptions قُصّرت** (qiyas + universities > 160 → ≤ 130).
- [x] **BreadcrumbList + HowTo schema** وصلت `[slug]/page.tsx` — HowTo لـ٦ مقالات فيها أدوات.
- [x] **بناء TypeScript نظيف** (`tsc --noEmit` exit 0).

## نطاق التدقيق

قُرئت ٦ من ١٠ مقالات كاملةً (تقويم/رواتب/زكاة/حمل/BMI/دورة/قياس والتحصيلي) + هيكل blog.ts + seo.ts + editorial-policy. الاستنتاجات معمَّمة على العشرة.

## النقاط القوية (احتفظ بها)

1. ✅ **بنية موحّدة**: كل مقال = مقدّمة قصيرة + أداة + جداول + FAQ + مصادر + "اقرأ أيضاً"
2. ✅ **أدوات تفاعلية**: HijriConverter/ZakatCalculator/BMI/Pregnancy/Menstrual = تفوّق حقيقي على المنافس (سطور/موضوع بلا أدوات)
3. ✅ **مصادر رسمية مذكورة**: ca.gov.sa, ummulqura, etec, mof, WHO, ACOG, CDC
4. ✅ **تحذيرات YMYL موجودة**: "تنبيه طبي" في كل مقال صحي، "استشر عالماً" في الزكاة
5. ✅ **جداول مقارنة**: كل مقال به جدول واحد على الأقل — Featured Snippet مادّة خام
6. ✅ **Editorial Policy قوية**: صريحة، AR+EN، تُظهر شفافية للـE-E-A-T
7. ✅ **بنية فنية سليمة**: hreflang, sitemap, JSON-LD (Article/FAQ/Site), i18n

## الفجوات الحرجة (يجب سدّها قبل توسّع الإنتاج)

### 🔴 P0 — كاتب مجهول (أخطر ثغرة E-E-A-T)

كل ١٠ مقالات مُوقّعة `فريق مقالات`. Google في فبراير ٢٠٢٦ أضاف قسم Authors في Search Central صريح: **YMYL بدون كاتب موثّق = جودة منخفضة**. مقالاتنا: ٧ من ١٠ YMYL (رواتب/زكاة/حمل/دورة/BMI/تحصيلي/جامعات).

**الأثر**: خطر رفض AdSense تحت "Low Value Content" + خطر عدم فهرسة اليومي + عدم تنافس على كلمات YMYL أبداً.

### 🔴 P0 — Mayo Clinic مستشهَد بها ٤ مرات

في `pregnancy-calculator-guide` + `bmi-calculator-guide` + `menstrual-cycle-calculator` + مقالات صحية. **Mayo يحجب الروبوتات (403)** — ذاكرة `health_citation_sourcing` مؤكَّدة بحادثة نبض الصفقات. Ahrefs يعتبرها روابط مكسورة، Google يحسم من الثقة.

**الحل**: استبدل بـ Harvard T.H. Chan Nutrition Source (nutritionsource.hsph.harvard.edu) — تعمل مع بشر+روبوتات (200 لكلا).

### 🔴 P0 — Person Schema غائب

`lib/seo.ts` `articleJsonLd` يستخدم `Organization` كـauthor فقط. **YMYL 2026 يتطلّب Person + credentials + sameAs (LinkedIn)**.

### 🟠 P1 — الادعاء الرقمي في مقال الرواتب غير محقّق

مقال `saudi-salary-dates-2026-2027` يقول:
- "رواتب المتقاعدين ٢٧ هجري" — لكن نتائج Google الحديثة تشير إلى **٢٥ ميلادي عبر GOSI** (بعد إصلاحات نظام التقاعد). قد يكون قديماً/خاطئاً — **يجب فحصه على mof.gov.sa/gosi.gov.sa قبل الاعتماد**.

**الأثر**: خطأ رقمي في مقال YMYL = خطأ فادح (Google Trust قاتل).

### 🟠 P1 — أنماط AI في الافتتاحيات

عيّنات من مقالاتنا:
- «يحتاج المستخدم العربي إلى التحويل بين الهجري والميلادي يومياً» (تقويم)
- «من أهم الأسئلة للأم الحامل: متى موعد الولادة؟» (الحمل)
- «مؤشر كتلة الجسم (BMI) أشهر مقياس عالمي...» (BMI)
- «الدورة الشهرية أساس معرفة صحة المرأة الإنجابية» (الدورة)

كلها **صيغ AI-typical**: تعريفية، غير محدّدة، بلا رأي أو مفارقة أو تفصيل. لا تكسب القارئ الجملة الثانية.

**الحل**: أعِد كتابة الافتتاحيات على نمط Voice Bible (فيتامين د السعودية): مفارقة + توطين محلي + سلطة بلا تكبّر.

### 🟠 P1 — لا استشهادات inline

المصادر تُذكر في قائمة نهاية المقال فقط. Google E-E-A-T يعطي وزناً أعلى لـ **inline citation** بجوار الادعاء. مثال حالي:

> "المصدر: World Health Organization — BMI Classification"

**الصحيح**: 
> "تصنيف WHO المعتمد ([WHO — BMI Classification](https://who.int)): BMI ≥ ٣٠ = سمنة درجة ١."

### 🟡 P2 — BreadcrumbList Schema غائب

`lib/seo.ts` بلا `breadcrumbJsonLd()`. Rich Results الافتراضية للمقالات تعطي فتاتاً — نخسر مساحة SERP.

### 🟡 P2 — HowTo Schema للأدوات

الأدوات (Zakat/BMI/Pregnancy Calculator) هي HowTo فعلياً. Schema.HowTo يمنحها ظهوراً محسّناً في نتائج البحث.

### 🟡 P2 — Cluster pages للصحة/المال معطّلة

`enabled: false` لـ health/finance/cars/tutorials/websites/fabrics. مقالات BMI/الحمل/الدورة تنتمي لـ `calendar` **زوراً** (لا معنى تصنيفياً — أدرجت هناك لأن `health` معطّل). يضرّ التنظيم الدلالي (topical authority).

### 🟡 P2 — Description بعض المقالات > 160 حرفاً

مثلاً مقال الرواتب description = ~165 حرفاً — Google يقطع عند 150-160 في SERP.

## الأولوية العملية المقترحة (بالترتيب)

### الجرعة الأولى (قبل أي مقال جديد)
1. **إنشاء persona كاتب رئيسية**: اسم حقيقي (المالك) + مؤهّل + صفحة `/author/[slug]` + LinkedIn
2. **تحديث `lib/seo.ts` articleJsonLd**: `author: Person` مع sameAs
3. **إضافة `breadcrumbJsonLd()` helper**
4. **استبدال Mayo Clinic** بـHarvard Nutrition Source في ٤ مقالات صحية
5. **تفعيل cluster `health`** + نقل المقالات الصحية إليه

### الجرعة الثانية (تحسين موجود)
6. **إعادة كتابة الافتتاحيات الأربع** التي رصدنا فيها نمط AI
7. **تحويل مصادر النهاية إلى inline citations**
8. **تحقّق فعلي من رقم "٢٧ هجري لمتقاعدين"** — تحديث المقال بما يصدر عن mof.gov.sa/gosi
9. **إضافة `HowTo` schema** للمقالات الست التي فيها أداة
10. **تشذيب descriptions الطويلة**

### الجرعة الثالثة (توسّع)
11. كتابة ٥-١٠ مقالات جديدة على البلاي بوك الجديد
12. تقديم AdSense (بعد الوصول ٢٠ مقال + الجرعة الأولى مكتملة)

## ما لا يجب فعله

- ❌ لا تكتب مقالات جديدة بنفس نمط "فريق مقالات" — نضيف ديناً تقنياً كل مقال
- ❌ لا تسـتشهد بـ Mayo Clinic
- ❌ لا تفتح افتتاحية بـ"يحتاج المستخدم" / "من أهم" / "يعدّ من أبرز"
- ❌ لا تضع مقال صحة/مال في cluster `calendar` مؤقّتاً — فعّل الـ cluster الصحيح أولاً
