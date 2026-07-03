---
name: blog_toys_cluster_progress
description: تقدّم عنقود مقالات الألعاب (المستهدَف ٧٢ مقال = ٢٤ قسم فرعي × ٣) — ما أُنجز وما تبقّى للجلسات القادمة
metadata:
  type: project
originSessionId: 3dc0c514-5670-41ee-9878-deb2d28e48c2
---
**التاريخ:** 2026-07-03. **الطلب:** ٧٢ مقال ألعاب (٢٤ قسم من AliExpress × ٣ لكل قسم) بصوت خبير ٢٠ سنة، بادئة `kids-toys-` لعمل bonus الـHub، متاجر مركزية: **ماماز آند باباز** (١٥٪ أوّل طلب) + **بيتي شوب** (١٠٪) + **نون** (٥٪) + **علي إكسبريس**.

## المُنجَز (١٠/٧٢)

### دفعة ١ (web `a6b0554`) — Pillar + STEM
1. `kids-toys-buying-guide-saudi-arabia` — Pillar شامل (سلامة CE/EN71/ASTM/GSO، BPA-Free، عمر، بطاريات، متانة)
2. `kids-toys-stem-educational-guide-saudi-arabia`
3. `kids-toys-robotics-coding-guide-saudi-arabia`
4. `kids-toys-science-experiments-guide-saudi-arabia`

### دفعة ٢ (web `3206bcb`) — قطيفة
5. `kids-toys-plush-stuffed-guide-saudi-arabia`
6. `kids-toys-plush-safety-cleaning-guide-saudi-arabia`
7. `kids-toys-plush-fashion-doll-guide-saudi-arabia`

### دفعة ٣ (web `5c84e8c`) — رضّع
8. `kids-toys-baby-newborn-guide-saudi-arabia`
9. `kids-toys-baby-teething-sensory-guide-saudi-arabia`
10. `kids-toys-baby-milestone-6-18m-guide-saudi-arabia`

## المتبقّي (٦٢/٧٢) — ٢١ قسم فرعي × ٣

**أولوية أولى (طلب سعودي عالٍ):**
- دمى الطفل والولد الجديد (baby-dolls) — ٣
- المطبخ والطعام والخدمات المنزلية (play-kitchen) — ٣
- لعب الأدوار المهنية والحياة (role-play) — ٣
- الفنون والإبداع (arts-crafts) — ٣
- الحركة والنشاط الإجمالي (gross-motor / outdoor) — ٣
- إلكترونيات الأطفال (kids-electronics) — ٣

**أولوية ثانية:**
- ألعاب الطاولة والبطاقات (board-card-games) — ٣
- شخصيات الحيوانات والديناصورات (animals-dinosaurs) — ٣
- اللغة ومحو الأمية (language-literacy) — ٣
- مركبات RC الأرضية (rc-vehicles) — ٣
- الألعاب البصرية والعلمية (visual-scientific) — ٣

**أولوية ثالثة:**
- بيوت الدمى والأثاث (dollhouses) — ٣
- ألعاب كلاسيكية وحركة (classic-action) — ٣
- مجموعات متقدمة وموضوعية (themed-sets) — ٣
- الحيل السحرية والدعائم (magic-props) — ٣
- الدمى والمسارح (puppets-theater) — ٣

**أولوية رابعة (نيتش):**
- ملابس وإكسسوارات الدمى (doll-clothes) — ٣
- دمى الموضة والتحصيل (fashion-collectible-dolls) — ٣
- شخصيات الأنمي وACG (anime-acg) — ٣
- ACG ومقتنيات الألعاب (acg-collectibles) — ٣
- سلاسل المفاتيح والقلائد القطيفة (plush-keychains) — ٣

## قواعد الكتابة المستقرّة

- **بادئة `kids-toys-`** لتفعيل bonus الـHub في `getRelatedPosts`.
- **صوت خبير ٢٠+ سنة:** شهادات (CE/EN71/ASTM)، ألوان طلاء (Water-Based Non-Toxic)، خامات (BPA-Free، Phthalate-Free، Food-Grade Silicone)، مقاييس ديسيبل (<٦٠ للأصوات)، أعمار محدّدة بشرح تنموي.
- **الأسعار وصفية ٤ فئات** (اقتصادية/متوسّطة/متقدّمة/فاخرة) بلا أرقام مفبركة.
- **الربط الداخلي:** كل مقال يشير للـPillar (`kids-toys-buying-guide`) + مقالَين شقيقَين + [ماماز آند باباز] + [بيتي شوب] + `/calendar`.
- **صيغة body:** template literal بأسطر حقيقية، صفر triple backticks، **صفر backtick واحد داخل body** (سبب كسر SWC parser — دُوّن في [feedback_no_backticks](feedback_no_backticks_in_template_literals.md)).
- **علي إكسبريس:** ينبّه دائماً بـ«⚠️ تحقّق من شهادات السلامة» لتحسّس المستخدم.

## هيكل المقال النموذجي

1. مقدّمة سياقية (١-٢ فقرة)
2. أنواع المنتج (٣-٦ فئات جدولية)
3. جدول مقارنة (Markdown table)
4. اعتبارات السلامة والعمر
5. اختبارات جودة قبل الشراء
6. أخطاء شائعة
7. أسعار وصفية (٤ فئات)
8. متاجر
9. أسئلة شائعة (٥-٦ أسئلة)
10. خلاصة + روابط داخلية

## عند استئناف الجلسة

1. اقرأ هذه الوثيقة + [feedback_no_backticks](feedback_no_backticks_in_template_literals.md).
2. `git -C dealpulseksa-web pull` (تأكّد آخر نسخة).
3. اقرأ آخر مقال في `blog.ts` عشان تُحسّ النغمة.
4. استمرّ من "أولوية أولى" أعلاه، ٣ مقالات لكل دفعة.
5. `tsc --noEmit` بعد كل دفعة قبل الدفع.
6. حدّث هذه الوثيقة بعد كل دفعة.

## المتاجر (URLs المستخدَمة)

- ماماز آند باباز: `/store/%D9%85%D8%A7%D9%85%D8%A7%D8%B2%20%D8%A2%D9%86%D8%AF%20%D8%A8%D8%A7%D8%A8%D8%A7%D8%B2`
- بيتي شوب: `/store/%D8%A8%D9%8A%D8%AA%D9%8A%20%D8%B4%D9%88%D8%A8`
- نون: `/store/%D9%86%D9%88%D9%86`
- علي إكسبريس: `/store/%D8%B9%D9%84%D9%8A%20%D8%A7%D9%83%D8%B3%D8%A8%D8%B1%D8%B3`
