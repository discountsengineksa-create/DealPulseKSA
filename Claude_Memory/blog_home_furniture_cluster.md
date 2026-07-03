---
name: blog_home_furniture_cluster
description: عنقود أثاث المنزل (٦ مقالات) بمدوّنة الويب — هَب + ٥ أدلّة تخصّصية بصوت خبير ٢٠ سنة، مربوطة بمتجر سيدار
metadata:
  type: project
originSessionId: 3dc0c514-5670-41ee-9878-deb2d28e48c2
---
**التاريخ:** 2026-07-03. **القرار:** عنقود أثاث ثانٍ بعد نجاح عنقود الأزياء (web `3409215` + `a05dc2b`).

## المقالات الستّة (بادئة `home-furniture-` لعمل bonus الـHub في `getRelatedPosts`)

1. **home-furniture-buying-guide-saudi-arabia** (Pillar) — الخامات (خشب صلب/Plywood/MDF/حبيبي/قشرة)، سلوك الأثاث في مناخنا (Kiln-Dried، تكييف، ملوحة ساحلية)، Martindale للأقمشة، قواعد القياس (الباب/المصعد/الزوايا)، الضمان.
2. **home-furniture-sofa-majlis-guide-saudi-arabia** — الهيكل، الزنبركات (8-Way Hand-Tied vs Sinuous vs Webbing)، كثافة فوم HR (٣٥+ كغ/م³)، قماش Martindale ٤٠K+، مقاسات المجلس السعودي.
3. **home-furniture-bed-mattress-guide-saudi-arabia** — أنواع المراتب (زنبركية Bonnell/Pocket، فوم Memory، هجينة، لاتكس)، جدول الصلابة حسب الوزن×طريقة النوم، مقاسات الأسرّة، الوسائد والملايات.
4. **home-furniture-dining-guide-saudi-arabia** — قاعدة ٦٠سم/شخص لسعة الطاولة، خامات الأسطح (خشب/زجاج/رخام/كوارتز/ميلامين)، ارتفاع الكراسي القياسي (٤٥–٤٦سم)، مسافات الغرفة.
5. **home-furniture-wardrobe-guide-saudi-arabia** — منزلق/مفصلي/Walk-in، توزيع الداخل ٤٠/٣٠/٢٠/١٠، MR-MDF لمقاومة الرطوبة، ملحقات LED ومفصلات Blum/Hettich.
6. **home-furniture-outdoor-guide-saudi-arabia** — Aluminum Powder-Coated، HDPE Rattan UV-Stabilized، Sunbrella (Solution-Dyed)، حماية من الرمال والملوحة والرياح.

## قرارات معمارية

- **صوت خبير ٢٠+ سنة:** مصطلحات فنية موصولة بأسبابها (Kiln-Dried، Martindale، HR Density، Pocket Springs)، تحذيرات محلية (تكييف Riyadh، ملوحة Jeddah)، اختبارات ميدانية (رفع طرف الكنب، الجلوس ١٥ دقيقة على المرتبة). لا شرح مبتدئ.
- **الأسعار وصفية بالكامل:** ٤ فئات (اقتصادية/متوسّطة/متقدّمة/فاخرة) مربوطة بأرقام تقنية (Density، Gauge، Martindale) — منسجم مع نمط عنقود الأزياء (بلا فبركة).
- **الربط الداخلي:**
  - كل مقال يشير للهَب (`home-furniture-buying-guide-*`) + مقالَين شقيقَين على الأقل.
  - الهَب المحوري `online-shopping-savings-guide-saudi-arabia` (سطر 61) صار يذكر الستّة.
  - الهَب الفرعي `home-shopping-guide-saudi-arabia` (سطر 656) يشير للعنقود.
- **المتاجر:** **سيدار** (متخصّص أثاث، تركيب+توصيل مجاني) هو المتجر المركزي؛ يليه **بيتي شوب** (١٠٪) و**نون** (٥٪) و**علي إكسبريس** (إكسسوارات فقط، محذّر منه للأثاث الرئيسي بسبب الشحن والضمان).
- **صيغة body:** template literal بأسطر حقيقية (لا `\n` حرفية)، صفر ``` (فحص Grep قبل الدفع)، صفر single-quoted body لتجنّب فخّ الفاصلة.

## الإصدار

- Web commit **`92f541f`** (main، دفع مباشر لـVercel prod).
- إضافة ٨٣٥ سطر لـ`lib/blog.ts`؛ TypeScript check نظيف؛ صفر backticks ثلاثية.

## المتبقّي (للمالك)

- **طلب فهرسة GSC** لكل من الستّة يدوياً (workflow قسم «🔎 الفهرسة» بالداشبورد يسحبها تلقائياً من sitemap عند تجديد ISR — قد يصل يوماً).
- **الترويج للباكلينك** كأصل مرجعي (أدلّة سعودية، منتديات ديكور، Pinterest).
- **مراقبة زحف Ahrefs** لأي orphan (كل مقال مربوط داخلياً من الهَب + شقيقيْن على الأقل — لا orphan متوقّع).

## الدروس

- **بادئة موحّدة للعنقود** (`home-furniture-`) تفعّل bonus الـHub في `getRelatedPosts` تلقائياً وتحوّل "الترتيب" إلى بنية طبيعية.
- **العمق التقني يفرق:** ذكر Martindale/HR Density/Kiln-Dried يحوّل المقال من عام إلى مرجعي — ضروري لبناء E-E-A-T (Expertise/Experience) بدون مؤلّف فردي.
- **مصادر معلومات:** كل الأرقام (Martindale، عدد زنبركات، ارتفاعات قياسية، مقاسات أسرّة) معايير عالمية معروفة — لا فبركة، صفر ادعاء مستحيل التحقّق منه.
