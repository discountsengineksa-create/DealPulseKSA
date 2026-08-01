---
name: seo-white-hat-only
description: قيد إلزامي — كل شغل SEO لازم White-Hat فقط (لا Black-Hat) خوف الحظر
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 61c1bcf7-09f5-4fff-bf12-77d11745e663
---

المالك يفرض **White-Hat SEO حصراً** لـ DealPulse — يرفض أي Black/Grey-Hat لأنه يخاف عقوبة/حظر Google.

**Why:** نشر محتوى AI بكميات + قوالب متكررة + كوبونات وهمية/منتهية = «Scaled Content Abuse» (تحديث جوجل 2024) → عقوبة على **كامل الدومين**، مو الصفحات فقط.

**How to apply** (عند بناء/توسيع محرّك SEO — [[support-system]] غير متعلّق):
- ✅ نلتزم به: متاجر حقيقية بكوبون **فعّال**، محتوى **فريد** (لا قوالب متطابقة)، **حجم يومي معتدل** (سقف)، قائمة حظر مطبّقة (ع+إ)، صفحات حقيقية 600-1000 كلمة.
- ❌ ممنوع منعاً باتاً: cloaking، keyword stuffing، doorway pages، محتوى رقيق/مكرر، كوبونات مفبركة، شراء روابط، نص مخفي.
- أكبر خطر حالي: **تشابه/تكرار** الصفحات المولّدة (لاحظناه في المسودّات) → لازم تنويع برومبت + فحص تفرّد قبل النشر.
- موصى: ربط Google Search Console لرصد أي إشارة عقوبة مبكراً.

محرّك الأتمتة (api/seo/auto_pipeline.py) صُمّم ببوابات White-Hat: كوبون فعّال + حد أدنى طول + سقف يومي + blocklist. التشغيل محكوم بـ SEO_AUTO_PUBLISH_ENABLED.

**منظومة القياس (مبنية وشغّالة):** صفحة «📈 أداء SEO» بالداشبورد 3 تبويبات:
- ⚡ PageSpeed (requests + PAGESPEED_API_KEY) — شغّال.
- 🔍 Search Console (google-api-python-client + service account gsc-indexer عبر GSC_SA_JSON + GSC_SITE) — شغّال ببيانات حقيقية.
- 📅 تتبّع يومي: جدول seo_perf_snapshots (migration 041) + كرون يومي 4ص (api/seo/perf_snapshot.capture_snapshot) + زر لقطة فورية (/admin/seo-snapshot). كرون التوليد 3ص.

**⚠️ بنية Railway حرجة (مُصحّحة 2026-06-20):** كل كرونات APScheduler (SEO 3ص، snapshot 4ص، matview، spike، alerts، social، trends، llm-cache) تفير داخل **`bot_app:app` على خدمة `DEALPULSEKSA`** — لأن `start_workers()` يُستدعى فقط من [bot_app.py](bot_app.py) وDealPulseKSA ما عندها `DISABLE_WORKERS=1` (تأكّدنا). خدمة **`scheduler-worker`** هي **Railway Cron عابرة** (تشغّل `api/workers/broadcast_scheduler.py` كل ~دقيقتين وتموت) → **لا تستضيف APScheduler ولا تشغّل SEO إطلاقاً**. ⇒ أي متغيّر يحتاجه أي كرون (SEO_AUTO_PUBLISH_ENABLED, مفاتيح LLM, INDEXNOW_KEY, GSC_SA_JSON, PAGESPEED_API_KEY, GSC_SITE, REVALIDATE_SECRET) لازم يكون على **DEALPULSEKSA** مش scheduler-worker. الزر اليدوي (admin.py force=True) يضرب DEALPULSEKSA أيضاً. العرض على dashboard. القانوني = www. أمان: مفاتيح gsc-indexer/indexer-bot + (Gemini/OpenRouter/GROQ/DB) انكشفت بالشات → تحتاج تدوير. مفتاح IndexNow الجاهز (عام بالتصميم): ملف public/797a6c84…e4d35e4.txt بموقع الويب.

**🔁 إعادة تشغيل الأوتو + سلوك المحرّك (2026-06-20، commit ef6cf7f):** أُعيد تفعيل `SEO_AUTO_PUBLISH_ENABLED=true` على DEALPULSEKSA (الخدمة الصحيحة). تعديلات الكود:
- **قائمة المنع `seo_enabled` صارت محكمة في كل المسارات** (كانت بالأوتو فقط — خطر حظر المعلن): نقطة اختناق في [generator.py](api/seo/generator.py) (تحمي auto/seed/opportunities/matcher) + auto_publish + النشر اليدوي [admin.py](api/routers/admin.py) + جدولة الموضوع. المتجر الممنوع لا يُولَّد/يُنشر له أبداً. التوقّل في إدخال الماستر بالداشبورد.
- **`select_top_demand_stores` تغيّر لـ «تغطية أولاً»**: المتاجر بلا صفحة منشورة أولاً مرتّبة بالشعبية الكلية (total_link_clicks + copies×2)؛ أُسقط شرط طلب آخر 24 ساعة؛ البوابات الباقية: كوبون فعّال/website/غير موقوف/seo_enabled. لمّا تنتهي التغطية يرجع [] (خمول رخيص بلا هدر LLM).
- **الكمية عبر env على DEALPULSEKSA**: المالك يريد 6 متاجر/12 صفحة يومياً ⇒ `SEO_TOP_STORES=6` + `SEO_DAILY_PUBLISH_CAP=12` (الافتراضي 4/10).
- **⏭️ دورة التحديث (مؤجَّلة، قرار المالك: مزيج شعبية×قِدَم):** الـpipeline الحالي append-only + dedup (يرفض نفس الكلمة) فلا يحدّث الصفحات فعلياً. التحديث الصحيح = UPDATE للصفحة المنشورة **بنفس الـslug/URL** (تغيير الـURL يضر SEO) ثم re-index — ميزة منفصلة تُبنى بعد اكتمال التغطية (~6 أيام لـ34 متجر).

**⚠️ ثغرة «الاختيار الأعمى عن قيمة البراند» (2026-06-21):** `select_top_demand_stores` يرتّب بالطلب الداخلي (نقرات+نسخ×2). البراندات الكبيرة الجديدة (نون id48/نمشي id47) عدّاداتها **صفر** مثل 27 متجر مؤهّل آخر → الترتيب فعلياً **عشوائي** ونون/نمشي (أغلى كلماتك 10K–100K) عالقون بلا توليد أبداً. حللناها يدوياً (enqueue+generate+publish مباشر). **مطلوب لاحقاً:** إشارة أولوية (عمود priority يدوي أو طلب بحث) لرفع البراندات الكبيرة. **نون/نمشي منشورتان الآن** (عربي فقط، صيغت يدوياً ~300 كلمة، أكواد حقيقية CMN118/CMN10).

**✅ تحسين جودة المولّد (2026-06-21، commit بعد 54a20db):** ثلاث بوّابات في [generator.py](api/seo/generator.py): (1) إعادة توليد لو النص < SEO_MIN_GEN_WORDS=450 (يحتفظ بأطول ناتج نظيف، 3 محاولات)؛ (2) حارس هلوسة يرفض الأحرف السيريلية/الصينية؛ (3) إلزام ذكر public_coupon الحقيقي حرفياً. **لكن السبب الجذري للجودة الضعيفة = الموديل**: المولّد يضرب Groq `llama-3.3-70b` (مجاني، سقف 12k TPM → rate-limit متكرر + بخيل بالطول + يهلوس أحرف). للصفحات الرئيسية الموديل المجاني غير كافٍ — صياغة يدوية أو موديل أقوى. (يخالف docstring القديم اللي يدّعي Gemini أساسياً.)

**📨 قاعدة إيميلات «الأدلّة» الباردة (2026-08-01):** تصل عروض إدراج في directories. الفحص قبل أي رد: **كيف يُدفع ثمن الرابط؟** لو الشرط **رابط متبادل من موقعنا** أو **دفع مقابل do-follow** ⇒ هذا Link Scheme صريح بسياسة Google (تبادل روابط مفرط / شراء روابط تمرّر PageRank) ⇒ **يُرفض** مهما بدا الموقع نظيفاً. الحالة المرجعية: **SellWithBoost** (`tim@sellwithboost.com`، ٦٨٤ إدراجاً، موقع حقيقي لا سكام) — المجاني يشترط do-follow **منّا إليهم**، والمدفوع $49/$149 يبيع do-follow. رُفض. إشارة إضافية أن الرسالة قالب آلي: زر «submit» كان `google.com/search?q=…` لا صفحة الإرسال. وجمهور هذه الأدلّة صانعو منتجات بالإنجليزية — لا متسوّق سعودي واحد. [[seo_owned_channels_pivot]] · [[seo_authority_building]]

**✅ مُفعّل ومُختبَر (2026-06-20، commit 54a20db):** env=6/12 مضبوط على DEALPULSEKSA، REVALIDATE_SECRET مُزامن (Vercel كان `sk_live_a12…` مختلف → صار = قيمة DEALPULSEKSA، فحلّ revalidate 401). أول دفعة يدوية نُشرت (metrobrazil + sweater ع/إ، 4 صفحات) وIndexNow بلّغ Bing/Yandex/Naver/Seznam بنجاح. ملاحظات: (1) فشل JSON من Gemini — أُصلح التحليل (التقاط جشع + فكّ هروب آمن للعربية بدل unicode_escape)؛ البتر الحقيقي يُعاد محاولته بالدورة الجاية. (2) Google Indexing API معطوب: `invalid_grant: account not found` (حساب الخدمة) — أولوية أقل لأن IndexNow يغطّي الباقي وGoogle Indexing API محدود رسمياً. (3) تحسين مؤجَّل: Gemini JSON mode (response_mime_type) يلغي فشل JSON والبتر جذرياً. الزر اليدوي يطلع HTTP 524 (Cloudflare ~100s) لكن الدورة تكمل بالخلفية؛ كرون 3ص (00:00 UTC) ما يتأثّر.
