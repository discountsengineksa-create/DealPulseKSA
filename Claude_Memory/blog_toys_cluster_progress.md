---
name: blog_toys_cluster_progress
description: تقدّم عنقود مقالات الألعاب (المستهدَف ٧٢ مقال = ٢٤ قسم فرعي × ٣) + قسم الهواتف والإكسسوارات القادم
metadata:
  type: project
originSessionId: 3dc0c514-5670-41ee-9878-deb2d28e48c2
---
**التاريخ:** 2026-07-04. **الطلب:** ٧٢ مقال ألعاب (٢٤ قسم × ٣) بصوت خبير، بادئة `kids-toys-`، متاجر: ماماز آند باباز/بيتي شوب/نون/علي إكسبريس. **بعد الانتهاء:** قسم الهواتف والإكسسوارات بنفس المنهج.

## المُنجَز (٢٨/٧٢)

### الأقسام الفرعية المكتملة (٩ من ٢٤):
1. **Pillar** (١): kids-toys-buying-guide-saudi-arabia
2. **STEM** (٣): stem-educational, robotics-coding, science-experiments
3. **قطيفة** (٣): plush-stuffed, plush-safety-cleaning, plush-fashion-doll
4. **رضّع** (٣): baby-newborn, baby-teething-sensory, baby-milestone-6-18m
5. **مطبخ لعب** (٣): play-kitchen, play-food-utensils, tea-set-baking
6. **لعب أدوار مهنية** (٣): role-play, doctor-medical-kit, tools-workshop
7. **فنون وإبداع** (٣): arts-crafts, crayons-markers, playdough-clay
8. **حركة/خارجي** (٣): gross-motor-outdoor, bikes-scooters, ride-on
9. **دمى الأطفال** (٣): baby-dolls, baby-doll-accessories, baby-doll-stroller-nursery
10. **طاولة/بطاقات/شطرنج** (٣): board-games, card-games, chess-strategy

## المتبقّي (٤٤/٧٢) — ١٥ قسم فرعي × ٣

**أولوية أولى:**
- إلكترونيات الأطفال (kids-electronics) — ٣
- مركبات RC (rc-vehicles) — ٣
- شخصيات الحيوانات والديناصورات (animals-dinosaurs) — ٣
- اللغة ومحو الأمية (language-literacy) — ٣

**أولوية ثانية:**
- الألعاب البصرية والعلمية (visual-scientific) — ٣
- بيوت الدمى (dollhouses) — ٣
- ألعاب كلاسيكية وحركة (classic-action) — ٣
- مجموعات متقدمة وموضوعية (themed-sets) — ٣

**أولوية ثالثة (نيتش):**
- الحيل السحرية والدعائم (magic-props) — ٣
- الدمى والمسارح (puppets-theater) — ٣
- ملابس وإكسسوارات الدمى (doll-clothes) — ٣
- دمى الموضة والتحصيل (fashion-collectible-dolls) — ٣
- شخصيات الأنمي وACG (anime-acg) — ٣
- ACG ومقتنيات (acg-collectibles) — ٣
- سلاسل المفاتيح القطيفة (plush-keychains) — ٣

## القسم القادم بعد الألعاب: الهواتف والإكسسوارات

المستخدم أرسل شاشة قسم AliExpress للهواتف (2026-07-04) — نفس المنهج ٣ مقالات لكل قسم فرعي:
- الهواتف المحمولة، حافظات (واقية/موضة/محافظ/مخصّصة/مزخرفة)
- شواحن ومحولات، بنوك طاقة، كابلات
- ملحقات SIM
- ملحقات التصوير (فلاشات/عدسات/سلفي/حوامل)
- واقيات الشاشة، مبردات الهاتف، أدوات النقر التلقائي، معززات الإشارة

## قواعد الكتابة المستقرّة

- بادئة `kids-toys-` (والقسم القادم `phone-accessories-` أو مشابه).
- **صفر backtick** داخل body (حتى واحد يكسر SWC — حادثة 2026-07-03).
- أسعار وصفية ٤ فئات (اقتصادية/متوسّطة/متقدّمة/فاخرة).
- ربط داخلي: Pillar + شقيقتان + متاجر + `/calendar`.

## دَرس التزامن بين الجهازين

الجهاز الآخر يدفع بشكل نشط للغاية (أزياء رجالية/نسائية، أحذية، جمال، مجوهرات). **قبل كل دفعة:** `git fetch && git log --oneline HEAD..origin/main`. **عند التعارض:** استخرج المقالات كنصّ، `reset --hard origin/main`، أعِد الإدخال قبل `];`. نمط ثابت بلا فقد للعمل.

## عند استئناف الجلسة

1. `git pull` في dealpulseksa-web أوّلاً.
2. اقرأ هذه الوثيقة + [feedback_no_backticks](feedback_no_backticks_in_template_literals.md).
3. اقرأ آخر مقال في `blog.ts` عشان تُحسّ النغمة.
4. استمرّ من "أولوية أولى" أعلاه، ٣ مقالات لكل دفعة.
5. `tsc --noEmit` بعد كل دفعة قبل الدفع.
6. حدّث هذه الوثيقة بعد كل دفعة.
