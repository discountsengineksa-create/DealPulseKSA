---
name: health_content_cluster
description: عنقود المحتوى الصحي بمدوّنة الويب (10 مقالات مكمّلات) لفتح تصنيف iHerb «محتوى» 5% + كود مكافآت QQC1568
metadata: 
  node_type: memory
  type: project
  originSessionId: b982bbc2-2107-4339-a759-ee4be1b52729
---

نُشر **عنقود محتوى صحي = 10 مقالات** بمدوّنة الويب (2026-06-15، commit fe33c45 بريبو dealpulseksa-web). الهدف: يدفع iHerb لتصنيف الموقع **«محتوى» (عمولة 5%) لا «كوبونات» (1%)**، ويبني سلطة موضوعية (topical authority) — أساس قبول iHerb بعد رفض سابق.

**أين:** مصفوفة `posts` في [lib/blog.ts] بريبو dealpulseksa-web (مو DB ولا داشبورد). كل مقال كائن `BlogPost` ثنائي اللغة (عربي canonical + `_en`). النشر = إضافة كائن + push على main → Vercel/Railway يبني. العارض [BlogPostContent.tsx] ماركداون-لايت: يدعم `## ` و`- ` و`[]()` و`**` فقط — **لا جداول ولا `>`** (تظهر كرمز).

**المقالات العشرة (slug):** vitamin-d / collagen / magnesium / omega-3 / vitamin-c / probiotics / hair-vitamins / creatine / multivitamin / whey-protein (كلها `-guide-saudi-arabia`).

**معايير الكتابة (مطلوبة من المستخدم):** نبرة متخصّص واثقة، **بلا مبالغة، بلا رموز/إيموجي**، لا ادعاءات طبية (YMYL)، إفصاح أفلييت + إخلاء طبي أعلى كل مقال، مصادر موثوقة (NIH ODS / Mayo / Cleveland / Harvard / ISSN / SFDA)، أسئلة شائعة، وربط داخلي بين المقالات. المنتجات حقيقية من «الأكثر مبيعاً» بالسعودية (دليل طلب فعلي)، والمواصفات من لوحة «نظرة عامة» بصفحة المنتج.

**التسييل:** كل روابط iHerb (28 رابطاً) تحمل **كود المكافآت `?rcode=QQC1568`** (رصيد متجر لا كاش، ضعيف: العميل ياخذ خصم الموقع 20% أكبر من 5% الكود).

**🔴 iHerb عبر Impact = مرفوض مرتين (2026-06-16، «Brand alignment mismatch»، رفض آلي شبه فوري)** رغم الموقع الموثّق + ملف Content/Reviews + المقالات العشرة كروابط. السبب = **جدار الترافيك/السجل الآلي** نفسه الذي رفض SHEIN/Trip.com/Kiwi/Etihad (انظر [[admitad_affiliate_setup]]) — لا علاقة له بجودة المحتوى. **القرار: لا تُعاد المحاولة الآن؛ تُؤجَّل 3-6 أشهر لين يصير ترافيك حقيقي.** (الإعداد على Impact: حساب DiscounEngineKsa، موقع DealPulseKSA موثّق بـmeta `impact-site-verification`=31274b97... في [layout.tsx]، Business Model=Content/Reviews.)

**البديل لتسييل المحتوى الصحي الآن:** Amazon Associates (أمازون السعودية، يقبل الجدد بشرط 3 مبيعات/180يوم) أو برامج مكمّلات أخرى — أو تجاهل التسييل مؤقتاً والمحتوى يبني السلطة/الترافيك. المبدأ الأكبر: الربح القريب من المتاجر التي تقبل الجدد ([[salla_affiliate_channel]] + AliExpress) لا البراندات الكبيرة الانتقائية. يرتبط بـ[[seo_white_hat_only]] و[[publish_channels_feature]].

**التالي:** عناقيد تتبع متاجر الأفلييت لا مواضيع عشوائية (مبدأ متّفق عليه): أزياء←SHEIN، سفر←Trip.com/الاتحاد/Airalo، تقنية←AliExpress. العمق أولاً (عنقود عنقود) لا الاتساع.
