---
name: Marketing Baseline & Strategy (2026-07-28)
description: Real traffic is ~121 Saudi humans/mo (web_visits is 89% bot noise); conversion WORKS (~16%); bottleneck is acquisition not conversion; brand-nav vs aggregator-intent SEO lesson; /national-day shipped
type: project
---

خط الأساس التسويقي الحقيقي لنبض الصفقات (سُحب من DB + Google Search Console عبر Windsor، 2026-07-28). المنصّة عمرها ~6 أسابيع (إطلاق ~13 يونيو 2026).

**الحقيقة الصادمة — «الزيارات» وهم:** `web_visits` يعرض ~3,961 زيارة/30يوم لكن **89% ضجيج** (73% is_datacenter، 90% country=US، 60% device_class='bot'). الحقيقة بعد التصفية: **429 زيارة بشرية (312 فريد)، منها 204 سعودية = 121 إنساناً سعودياً فريداً/شهر.** خانة `cf_bot_score` **فارغة 100%** (إثراء Cloudflare معطّل) ← اللوحة تعرض أرقاماً منتفخة. **لا تثق برقم web_visits الخام — صفِّ is_datacenter=false AND device_class IN ('mobile','desktop') AND country_code='SA'.** يتقاطع مع [[bot_vs_promo_heuristic]] و [[web_visits_tracking]].

**التحويل ليس مكسوراً — ممتاز:** 312 زائر بشري ← 50 فعل أفلييت (26 نسخ + 24 نقرة) ≈ **16%**. التتبّع سليم (`action_logs.source` = web/bot/telegram_miniapp؛ الويب 527 حدث). **البوتلنك 100% اكتساب (قمة القمع)، لا تحويل.** كل إنسان سعودي حقيقي تجيبه ≈ 16% منه يعمل فعل أفلييت — عائد محسوب.

**GSC (28 يوم):** 105 نقرة / 10,523 ظهور / CTR 1% / متوسط مركز 23.4. هذه تقريباً كل الترافيك البشري الحقيقي.

**درس النيّة (محوري):** نوعان من البحث —
1. **اسم البراند** («بيلاس» م5.6/327ظهور، «فوغا» م8، «ماماز» م9): تترتّب صفحة 1 لكن **صفر نقرة** — نيّة *تنقّل*، الباحث يريد المتجر لا موقع كوبونات. **لن تكسب نقرته أبداً.** العناوين مُحسَّنة أصلاً (store/[slug] generateMetadata) فلا مكسب CTR متبقٍّ هناك.
2. **نيّة الشراء** («كود خصم نمشي»): مركز 40–78 (صفحة 4–8) = سقف سلطة الدومين، عميق جداً للنقر.
3. **نيّة تجميعية** (/calendar م6 = 30 نقرة، مناسبات، «أفضل عروض», فئات): تكسب النقرة *وتترتّب*. **← ركّز هنا، لا على أسماء البراندات.**

**نُفِّذ هذه الجلسة:** صفحة مناسبة مستقلة `/national-day` (اليوم الوطني السعودي 96 = الأربعاء 23 سبتمبر 2026، موثّق) — نيّة تجميعية، أكواد حيّة من DB، Schema (Breadcrumb+ItemList+FAQPage)، مسجّلة بالسايت‌ماب ومربوطة من /calendar. حيّة 200 (web fcf5e81).

**القرار المعلّق (المالك):** الاكتساب خارج SEO — بذرة مدفوعة صغيرة في السعودية (سناب/تيك توك) + إيقاع ريلز/تيليجرام. هو الرافعة الأسرع لأن SEO buyer-intent مسقوف بالسلطة لأشهر. ملف السياق التسويقي: `.agents/product-marketing.md`. يتقاطع مع [[seo_authority_building]] و [[seo_indexation_status]] و [[content_programmatic_strategy]].
