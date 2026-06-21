# دليل تسريع الفهرسة — Google Search Console

> الهدف: رفع dealpulseksa.com من **4/139 صفحة مفهرسة** إلى تغطية كاملة.
> الحالة المرجعية: تشخيص GSC بتاريخ 2026-06-21 (حصار موقع جديد + صفر باكلينك + ثقة دومين صفر = ميزانية زحف شبه معدومة).
> القيد: White-Hat فقط. لا أدوات «فهرسة فورية» مدفوعة ولا حقن روابط.

---

## الفكرة بسطر واحد
طلب الفهرسة اليدوي **يدفع** قوقل لزيارة صفحاتك المهمة الآن بدل الانتظار شهوراً. لكنه **لا يضمن** الفهرسة — الفهرسة الدائمة تحتاج باكلينك + محتوى حقيقي (انظر `backlink_targets.md`). هذا الدليل = الجزء الذي تنفّذه بيدك خلال ~أسبوعين.

## الحصة اليومية (مهم)
أداة «فحص عنوان URL» في GSC تسمح بـ **~10 طلبات فهرسة يومياً** لكل موقع (حد ناعم). لا تحرقها على صفحات ضعيفة — رتّبها بالطبقات أدناه.

## الخطوات لكل رابط
1. GSC → أعلى الصفحة: ألصق الرابط في شريط **«فحص أي عنوان URL»**.
2. انتظر النتيجة → اضغط **«اختبار عنوان URL المباشر» (Test Live URL)**.
3. لو ظهر «العنوان URL متاح لـ Google» → اضغط **«طلب الفهرسة» (Request Indexing)**.
4. لو ظهر خطأ (404 / محظور / canonical) → سجّله وعالجه (انظر القسم الأخير).

---

## أولاً: تأكيدات أساسية (مرّة واحدة)
- [ ] GSC → **Sitemaps** → تأكّد أن `https://www.dealpulseksa.com/sitemap.xml` مُرسَل وحالته «نجاح». لو لا، أرسله.
- [ ] تأكّد أن النسخة المُتحقَّق منها هي **www** (مطابقة للـ`SITE_URL`) لا الجذر بدون www — وإلا تنقسم الإشارات.
- [ ] (اختياري) فعّل **IndexNow** لتغطية Bing/Yandex فوراً (قوقل لا يدعمه).

## الطبقة 0 — اليوم 1: الصفحات المحورية (Hubs)
هذي تمرّر السلطة لباقي الموقع. أرسلها كلها اليوم الأول:
- [ ] `https://www.dealpulseksa.com/`
- [ ] `https://www.dealpulseksa.com/stores`
- [ ] `https://www.dealpulseksa.com/deals`
- [ ] `https://www.dealpulseksa.com/trending`
- [ ] `https://www.dealpulseksa.com/blog`
- [ ] `https://www.dealpulseksa.com/faq`
- [ ] `https://www.dealpulseksa.com/how-it-works`
- [ ] `https://www.dealpulseksa.com/about` (تُفهرس أصلاً — لتأكيد العلامة)

## الطبقة 1 — اليوم 2: صفحات الطلب العالي (Money pages)
أعلى طلب من `keyword_demand_ksa` والموجود فعلاً بالكتالوج = **نون · نمشي · علي اكسبرس · علي بابا · سيدار · H&M**.
> ⚠️ هذول عندهم `/store/` فقط — **ما تولّدت لهم صفحات `/c/`** بعد (رغم تفعيل seo_enabled). توليد `/c/` لنون/نمشي = مهمة قادمة.
- [ ] `https://www.dealpulseksa.com/store/%D9%86%D9%88%D9%86`  (نون)
- [ ] `https://www.dealpulseksa.com/store/%D9%86%D9%85%D8%B4%D9%8A`  (نمشي)
- [ ] `https://www.dealpulseksa.com/store/%D8%B9%D9%84%D9%8A%20%D8%A7%D9%83%D8%B3%D8%A8%D8%B1%D8%B3`  (علي اكسبرس)
- [ ] `https://www.dealpulseksa.com/store/%D8%B9%D9%84%D9%8A%20%D8%A8%D8%A7%D8%A8%D8%A7`  (علي بابا)
- [ ] `https://www.dealpulseksa.com/store/%D8%B3%D9%8A%D8%AF%D8%A7%D8%B1`  (سيدار)
- [ ] `https://www.dealpulseksa.com/store/%D8%A7%D8%AA%D8%B4%20%D8%A7%D9%86%D8%AF%20%D8%A7%D9%85`  (H&M)
- [ ] `https://www.dealpulseksa.com/blog/best-coupons-saudi-arabia-2026`
- [ ] `https://www.dealpulseksa.com/blog/how-to-shop-online-saudi`
- [ ] `https://www.dealpulseksa.com/blog/vitamin-d-guide-saudi-arabia`
- [ ] `https://www.dealpulseksa.com/blog/oud-perfume-guide-saudi-arabia`

## الطبقة 2 — اليوم 3: صفحات الهبوط /c/ العربية (محتوى فريد قابل للفهرسة)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-toyou-2026`  (تويو)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-elegant-hub-2026`  (إليجنت هاب)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-golden-flora-2026`  (قولدن فلورا)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-top-beauty-2026`  (توب بيوتي)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-al-makhmaliyah-2026`  (المخملية)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-qatret-asal-2026`  (قطرة عسل)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-carxtreme-2026`  (كاركستريم)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-wolfix-2026`  (وولفيكس)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-sweater-2026`  (سويتر)
- [ ] `https://www.dealpulseksa.com/c/%D9%83%D9%88%D8%AF-%D8%AE%D8%B5%D9%85-metrobrazil-2026`  (مترو البرازيل)

## الطبقة 3 — اليوم 4: أبرز التصنيفات
- [ ] `https://www.dealpulseksa.com/category/%D8%A3%D8%B2%D9%8A%D8%A7%D8%A1`  (أزياء)
- [ ] `https://www.dealpulseksa.com/category/%D8%B9%D8%B7%D9%88%D8%B1`  (عطور)
- [ ] `https://www.dealpulseksa.com/category/%D9%85%D9%83%D9%8A%D8%A7%D8%AC`  (مكياج)
- [ ] `https://www.dealpulseksa.com/category/%D8%AA%D8%AC%D9%85%D9%8A%D9%84`  (تجميل)
- [ ] `https://www.dealpulseksa.com/category/%D8%A7%D9%84%D9%83%D8%AA%D8%B1%D9%88%D9%86%D9%8A%D8%A7%D8%AA`  (الكترونيات)
- [ ] `https://www.dealpulseksa.com/category/%D8%AC%D9%88%D8%A7%D9%84%D8%A7%D8%AA`  (جوالات)
- [ ] `https://www.dealpulseksa.com/category/%D8%B9%D8%A8%D8%A7%D9%8A%D8%A7%D8%AA`  (عبايات)
- [ ] `https://www.dealpulseksa.com/category/%D8%B9%D9%88%D8%AF%20%D9%88%20%D8%A8%D8%AE%D9%88%D8%B1`  (عود وبخور)
- [ ] `https://www.dealpulseksa.com/category/%D9%85%D8%AC%D9%88%D9%87%D8%B1%D8%A7%D8%AA`  (مجوهرات)
- [ ] `https://www.dealpulseksa.com/category/%D8%AC%D9%85%D8%A7%D9%84%20%D9%88%D8%B9%D9%86%D8%A7%D9%8A%D8%A9%20%D8%B4%D8%AE%D8%B5%D9%8A%D8%A9`  (جمال وعناية)

## الطبقة 4 — الأسبوع 2: الباقي على دفعات (10/يوم)
اسحبها بالترتيب من `/sitemap.xml`:
- [ ] **بقية المدوّنة** (عنقود المكمّلات): collagen · magnesium · omega-3 · vitamin-c · probiotics · hair-vitamins · creatine · multivitamin · whey-protein · beauty-skincare-guide · abaya-buying-guide · ramadan-deals-guide
- [ ] **بقية صفحات `/c/` العربية**: قطرة-عس · (وأي جديد يتولّد)
- [ ] **بقية المتاجر** `/store/…` (≈27) — الأكمل بياناتٍ أولاً
- [ ] **بقية التصنيفات** (≈18)
- [ ] **(اختياري) صفحات `/c/` الإنجليزية** (`…-en`) — أولوية أدنى (جمهور المغتربين فقط، لا يوجد مسار /en بعد)

---

## معالجة الـ404 الواحد (P1)
GSC أبلغ عن **رابط واحد يردّ 404**. الكود سليم (صفحات المتجر و`/c/` تستدعي `notFound()` صح)، فالأرجح رابط قديم/محذوف زحفه قوقل سابقاً.
1. GSC → **الصفحات (Pages/Indexing)** → افتح مجموعة **«لم يتم العثور عليها (404)»**.
2. انسخ الرابط بالضبط.
3. لو الصفحة يُفترض وجودها → أصلح المصدر الذي يشير لها. لو محذوفة عمداً → اتركها (404 طبيعي) أو أضف 301 لو لها بديل.
4. أرسل لي الرابط وأشخّص السبب الدقيق.

## بعد ~10–14 يوم: قِس النتيجة
- [ ] GSC → الصفحات → قارن عدد «المفهرسة» (كان 4) — هدف المرحلة: 30–50+.
- [ ] الأداء → هل ظهرت طلبات بحث غير اسم العلامة؟ (أول إشارة على كسر الحصار).
- [ ] أي صفحة بقيت «زُحفت ولم تُفهرس» = إشارة أنها تحتاج باكلينك/محتوى أقوى لا طلب فهرسة آخر.

> 🔑 الحقيقة الصادقة: طلب الفهرسة يفتح الباب، لكن **الباكلينك هو ما يبقي الباب مفتوحاً**. نفّذ هذا الدليل بالتوازي مع `backlink_targets.md`.
