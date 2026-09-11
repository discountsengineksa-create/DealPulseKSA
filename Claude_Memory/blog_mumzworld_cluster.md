---
name: blog_mumzworld_cluster
description: عنقود ممزورلد 20 مقالاً — master.id=93 كود M43 خصم 10%؛ حمل وأمومة ومواليد وأطفال؛ منضبط YMYL/سلامة (لا فورمولا، لا مقاعد سيارة، لا مصدات سرير، لا مكمّلات حمل) بنفس نمط النهدي؛ لم تُمسّ عناقيد ماماز آند باباز الشريكة
metadata:
  node_type: memory
  type: project
---

**٢٠٢٦-٠٩-١١** — المالك أرسل ~٢٢ لقطة من mumzworld.com/sa-ar وقال «سو السيو حق ممزورلد … اهتم لي كثير … عليه طلب عالي من الحوامل والأمهات الجدد» + طلب صريح: أمهات جدد + أسئلة وأجوبة + الحوامل والوسائد + مقارنات وجداول + ملابس المواليد والأطفال + «كن شامل».

## المتجر — ممزورلد (Mumzworld)

- `master.id=93` · `store_id='ممزورلد'` · `name_en='Mumzworld'` · `public_coupon='M43'` · **خصم 10%** · `my_coupon='6% للعملاء الجدد · 2% للحاليين'` (عمولة بوستيني الصحيحة — نفس عُرف [[blog_nahdi_cluster]]، ليست غلطاً) · `affiliate_link=mumzworld.com` · `store_tags={أطفال, أمومة و رضاعة, العاب, هدايا}` · `source_platform='بوستيني'` · `store_bio` مكتوب · `extra_offer='-'`.
- `/store/ممزورلد` لم يُفحص 200 صراحةً هذه الجلسة (نمط راسخ من ٩ متاجر بوستيني سابقة، لم يفشل مرة).
- **كود ثانٍ نُشر لاحقاً بطلب صريح:** `DISCOK95` خصم **25%** — كود برنامج «ادعي صديقة» الشخصي بحساب المالك (وجده بنفسه، ليس كود M43 العلني في `master`). المالك طلب صراحةً «أضف الكود الثاني … خصم 25%» ووضّح «وانا بضيفه في الماستر كود اضافي» — **نُشر في المحتوى (`94d7e5d`: الدليل المحوري + دليل الأكواد) بوصفه كود دعوة لا كوبون سلّة عام، والمالك يتكفّل بإضافته في `master` بنفسه (لا كتابة DB مني).**

## انضباط YMYL/السلامة (نفس صرامة [[blog_nahdi_cluster]])

استُثني صراحةً بالسبب:
- **حليب الأطفال الصناعي (الفورمولا)** — ظهر بارزاً في لقطات newmumz (NAN). لا مقارنة علامات، نوع التغذية قرار طبيب الأطفال.
- **مقاعد سيارة الأطفال** — ظهرت في newmumz. لا دليل شراء مفصّل، تُشترى جديدة معتمدة بتركيب احترافي فقط.
- **مصدّات/وسائد سرير الرضيع** — استُبعدت صراحة بسبب SIDS في `mumzworld-nursery-sleep-guide-saudi`، **مع تمييز واضح** أن وسائد الحمل (للأم) مختلفة تماماً وآمنة ومغطّاة.
- **مكمّلات الحمل (Pregnacare، حديد)** — ظهرت في لقطات وسائد الحمل. لا توصية نوع/جرعة، «قرار طبيبة الحمل».
- **أدوات نشاط الرضّع** (كرسي هزّاز، مشّاية) — إخلاء إشراف دائم + تحذير طبّي عام من المشّايات ذات العجلات.
- **اللعب الخارجي/المائي** — خوذة إلزامية + إشراف بالغ ملاصق قرب الماء دائماً.

## الـ20 مقالاً (`2b36d8d` — بادئة `mumzworld-`، فئة `أطفال`→kids عدا الكود `أدلّة التوفير`→savings-guides)

pillar `mumzworld-guide-saudi` · `mumzworld-pregnancy-essentials-guide-saudi` · **`mumzworld-pregnancy-pillow-guide-saudi`** (طلب صريح) · `mumzworld-maternity-clothes-guide-saudi` · `mumzworld-new-mom-essentials-guide-saudi` (طلب صريح) · `mumzworld-new-mom-faq-guide-saudi` (طلب صريح Q&A) · `mumzworld-strollers-guide-saudi` · `mumzworld-baby-carriers-guide-saudi` · `mumzworld-diaper-bags-guide-saudi` · `mumzworld-breastfeeding-essentials-guide-saudi` · `mumzworld-bottles-sterilizers-guide-saudi` · `mumzworld-baby-bath-skincare-guide-saudi` · `mumzworld-nursery-sleep-guide-saudi` · `mumzworld-newborn-clothes-guide-saudi` (طلب صريح) · `mumzworld-kids-clothes-guide-saudi` (طلب صريح) · `mumzworld-baby-gear-activity-guide-saudi` · `mumzworld-toys-by-age-guide-saudi` · `mumzworld-outdoor-kids-essentials-guide-saudi` · `mumzworld-potty-training-school-guide-saudi` · `mumzworld-coupon-m43-how-to-use-saudi`.

كل مقال: جدول مقارنة ≥١ (مطلوب صراحة)، FAQ بصيغة السؤال/الجواب الصحيحة، إفصاح أفلييت + إخلاء طبي/سلامة حيث يلزم، صفر رقم ريال رغم أن اللقطات فيها أسعار حقيقية ظاهرة (٢٠٢٦-٠٩-١١ — الانضباط يتجاهلها لأنها بايتة وقت النشر).

## de-orphan (٤ هَبّات — لم تُمسّ ماماز آند باباز)

`best-saudi-online-stores-2026` · `kids-toys-buying-guide-saudi-arabia` · `kids-toys-baby-newborn-guide-saudi-arabia` · `kids-toys-baby-doll-stroller-nursery-guide-saudi-arabia` (الأربعة عناقيد نبض الصفقات المحايدة، فيها أصلاً ذكر متعدّد متاجر بما فيها ماماز آند باباز — نمط راسخ). **تجنّبتُ عمداً أي `mamaspapas-*`** — عنقود شريك، [[blog_nazih_cluster]] يمنع الغزو.

## التحقّق

`esbuild --bundle lib/blog.ts` **EXIT=0** (قبل وبعد de-orphan) · ١٩٤٨ مقالاً إجمالاً · ٢٠ ممزورلد بلا حقول ناقصة · صفر slug مكرّر · صفر رابط `/blog/` مكسور · صفر FAQ ملتصق · صفر ``` أو `${` · **صفر باكتيك مهرَّب** (درس عنقود النهدي المُطبَّق: تحقّق برمجي قبل اللصق هذه المرة، صفر حادثة). روابط داخلية 4–22/مقال. **البناء الكامل لم يُشغَّل — فيرسيل مرجعي.**

## معلّق

- تحقّق `/store/ممزورلد` 200 لم يُنفَّذ صراحة (نمط راسخ بلا فشل سابق).

## تمّ لاحقاً (نفس الجلسة)

`blog_bridge` أُعيد بناؤه فعلياً — **١٧٢٤ صفّاً / ٧٦ متجراً** (ممزورلد ٢٠ + النهدي ٢٠ + ريف ١٨ كلها مؤكّدة بالعدّ الحيّ). كشف هذا خللاً حقيقياً في السكربت أُصلح — انظر [[feedback_harness_blocks_self_permission]] (قسم «تصحيح ٢٠٢٦-٠٩-١١»).

يكمّل [[blog_nahdi_cluster]] (نفس نمط YMYL بالضبط) · [[blog_reef_cluster]] · [[blog_nazih_cluster]] (حدود عناقيد الشركاء) · [[content_guardrails_playbook]] · [[voice_bible]] · [[blog_internal_link_deorphan]].
