---
name: blog_inline_code_chips
description: شارات الأكواد داخل المقالات — كل رابط /store/ يأخذ كوداً قابلاً للنسخ (إسناد-بالكود) أو CTA (إسناد-بالنقرة) على مستوى العارض
metadata:
  type: project
---

**المشكلة (2026-08-01):** المقالات تذكر المتاجر ونِسَب خصمها بلا **كود ولا زر** — الزائر يصل بنيّة شراء ثم يخرج بلا شيء ينسخه. الدليل من «صفحات الدخول» بالداشبورد: `/blog/kids-toys-smartwatch-guide-saudi-arabia` ١٧ زيارة · صفر تفاعل، و`/blog/cambodi-vs-hindi-oud-saudi-arabia` ٦٣ زيارة **كلها من بحث** · صفر تفاعل. المالك رصدها بصرياً بنفس اللحظة التي كشفها فيها التحليل. [[web_visits_tracking]]

**الحل — على مستوى العارض لا المحتوى:** تعديل واحد في `app/blog/[slug]/` (ريبو [[reconcile_web_repo_separately]]) يسري على كل المقالات بلا تحرير أي منها:
- `page.tsx`: `storeIdsIn(body)` يستخرج معرّفات `/store/…` من المتن، `buildStoreChips()` يجلب الكتالوج مرة واحدة (`getStores(500,'ar','full')`، كاش ٦٠ث) ويمرّر **المذكورين في هذا المقال فقط** (سقف زحف قوقل 2MB — [[web_blog_monolith_oom_and_client_prop_serialization]]).
- `BlogPostContent.tsx`: `storeChipHtml()` تُلحق الشارة بكل رابط متجر داخل `formatInline` (يغطّي الفقرات والقوائم والجداول والاقتباسات)، و`fixChipPunctuation()` تُعيد النقطتين لمكانها (`نون: 🎟️CMN118` بدل `نون 🎟️CMN118:`).

**الكشف يتبع الإسناد** ([[seo_meta_code_leak]] · `lib/seo/attribution.ts`): ٣٧ متجر إسناد-بالكود → زر ينسخ الكود في مكانه ويسجّل `copy_coupon` بـ`details='blog_inline_chip'`؛ ١١ متجر إسناد-بالنقرة (Admitad/AliExpress) → «🎟️ اعرض الكود» يقود لصفحة المتجر.

**مطبّان:**
1. **المعرّف من الرابط لا من نص الوصلة** — المقال يكتب «علي إكسبريس» بينما `store_id` = «علي اكسبرس».
2. **`public_coupon` ليس دائماً كوداً** — «استخدم الرابط للخصم» / «استخدم الرابط» نصّ إرشادي في نفس العمود (متجران). الفرز: كود حقيقي = بلا مسافات وطوله ≤ ٢٤.

**تحقّق:** `tsc` نظيف + `next build` ناجح محلياً (يحتاج `NODE_OPTIONS=--max-old-space-size=8192`) + **١٣٦٥ من ١٣٨١** صفحة مدوّنة تعرض شارة (٢٤٩٩ زر نسخ). الـ١٦ الباقية لا تذكر أي متجر في متنها: عنقود مكمّلات iHerb (فيتامين د/سي/أوميغا/كرياتين/بروتين/كولاجين/بروبيوتيك/مغنيسيوم/ملتي) + `best-coupons-saudi-arabia-2026` + `how-to-use-coupon-code-saudi` + `how-to-shop-online-saudi` + `online-shopping-savings-guide` + `ramadan-deals-guide` + `tools-home-solar-panels` + `phone-accessories-esim` — **فجوة تحويل مفتوحة** (iHerb ليس في `master` فلا رابط متجر له؛ كوده QQC1568 في [[health_content_cluster]]).

**How to apply:** أي تحسين تحويل للمدوّنة يُنفَّذ في العارض لا في `blog.ts` (٦.٥MB / ١٣٨١ صفحة). عدّ التغطية محلياً بـPowerShell على `.next/server/app/blog/*.html` — بحث `href="/store/` وحده يعطي ١٣٨١ لأن الفوتر يذكر ٢٠ متجراً في كل صفحة؛ العدّ الصحيح على `](/store/` (روابط المتن) أو `data-dp-chip`.
