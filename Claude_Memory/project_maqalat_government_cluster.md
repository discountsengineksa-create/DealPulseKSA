---
name: Maqalat Government Services Cluster
description: 2026-09-11 عنقود «الخدمات الحكومية السعودية» على maqalat.org — ١٥ موضوع × لغتين = ٣٠ مقال، مع حاسبة تفاعلية لمكافأة نهاية الخدمة وفق نظام العمل م.٨٤-٨٥
type: project
originSessionId: 245de921-acb1-4306-8d30-ea97bf4d3a03
---
عنقود جديد `government` على [maqalat.org](https://maqalat.org) — أعلى طلب بحث يومي في السعودية بعد الاسلاميّات والرياضة، لكنّه evergreen وآمن لـAdSense وE-E-A-T واضح (مصادر رسمية بلا YMYL دينية/طبية).

## ما شُحن (commit 25daa7f + c2d130e)

**١٥ موضوع × ٢ لغة = ٣٠ ملف MDX**، الحاسبة الوحيدة على «مكافأة نهاية الخدمة»:

1. `end-of-service-gratuity-calculator` — حاسبة (Article 84-85) + HowTo schema
2. `iqama-renewal-guide` — تجديد الإقامة
3. `absher-complete-guide` — أبشر الشامل
4. `saudi-id-renewal-guide` — تجديد الهوية
5. `traffic-violations-guide` — المخالفات + الاعتراض + النقاط
6. `gosi-pension-guide` — معاش التأمينات (نظامَين قديم وجديد ٢٠٢٤)
7. `saudi-labor-law-rights` — حقوق الموظف بالإحالة لمواد النظام
8. `kafala-transfer-guide` — نقل الكفالة + مبادرة تطوير علاقة العمل
9. `saudi-passport-guide` — الجواز
10. `najiz-services-guide` — ناجز
11. `driving-license-saudi-guide` — رخصة القيادة + الاستبدال
12. `tawakkalna-complete-guide` — توكلنا
13. `musaned-domestic-workers-guide` — مساند + الأجور المنزلية
14. `zatca-vat-e-invoicing-guide` — ZATCA + فتورة (المرحلتان)
15. `saudi-government-salary-scale` — سلّم الرواتب (مرتبة/درجة/بدلات)

## البنية التقنية

- **الحاسبة**: `components/EndOfServiceCalculator.tsx` — client-side، صفر إرسال بيانات، معامل الاستقالة يتغيّر تلقائياً بحسب المدّة
- **العنقود**: أُضيف `government` في `lib/clusters.ts` بأيقونة Landmark
- **مكوّنات MDX**: EndOfServiceCalculator مسجَّل في `mdx-components.tsx`
- **HowTo schema**: مضاف في `TOOL_HOWTO` بـ`app/[locale]/[slug]/page.tsx`
- **الميزات الجاهزة تلقائياً لكلّ مقال**: FAQPage schema من الـfrontmatter، ratings + comments + newsletter عبر `ArticleBelowFold`، related-articles، breadcrumb schema
- **الفهرسة**: `scripts/ping_government_cluster.mjs` — مستهدف بـ٣٠ URL فقط بدل كامل السايت ماب

## مبدأ الكتابة المطبَّق

كلّ مقال التزم بقاعدة «المبدأ الأول: الضرر لا Google» من writing playbook:
- **صفر فبركة أرقام**: حين تكون الرسوم متغيّرة (تجديد الإقامة، مكتب العمل، ZATCA) نُوجّه للشاشة الحيّة بدل تخمين قيمة
- **مصادر رسمية inline**: laws.boe.gov.sa (النصوص القانونية)، absher.sa، hrsd.gov.sa، gosi.gov.sa، zatca.gov.sa، najiz.sa، gdp.gov.sa
- **تحذير سلامة**: كلّ مقال قانوني/مالي يذكر «إعلامي فقط، راجع الجهة» صراحةً
- **جدول واحد على الأقلّ** في كل مقال (Featured Snippet target)
- **٥-٧ FAQ** في الـfrontmatter
- **٣ روابط داخلية** أسفل كلّ مقال + inline links

## المتبقّي (اختياري)

- **الكاتب المعتمَد**: كلّ الـ٣٠ مقال بتوقيع «مقالات»/«Maqalat» عام. لرفع E-E-A-T نحتاج شخصية موثّقة (محامٍ/محاسب) خصوصاً على YMYL (المكافأة، الضريبة، معاش التأمينات)
- **حاسبات إضافية** يمكن بناؤها لاحقاً:
  - GOSI Pension Estimator (نظام قديم + جديد)
  - Government Salary Calculator (مرتبة × درجة)
  - VAT Calculator (١٥٪ بسيط)

## أرقام السايت بعد الشحن

- المقالات: 228 → **258** مقال
- السايت ماب: 252 → **282** URL

## الفهرسة

- سكربت `ping_government_cluster.mjs` جاهز، يستهلك ٣٠ من الحصّة اليومية (٢٠٠)
- **يجب تشغيله بعد تأكّد الـdeploy على Vercel** لتفادي 404 يوقفه Google
- الأمر: `node scripts/ping_government_cluster.mjs`
