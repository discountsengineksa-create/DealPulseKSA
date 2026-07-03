---
name: story-system-design
description: التصميم النهائي لنظام ستوري المتاجر (story_slides) — النموذج المتداخل، الواجهتان، الفيديو/الصوت/الأداء/z-index
metadata: 
  node_type: memory
  type: project
  originSessionId: 122c2f20-d022-4f1d-928d-a1c400d4f948
---

نظام **ستوري المتاجر** (إنستقرام-ستايل) عبر الموقع + الميني-ويب + لوحة التحكم. حُسم بعد تكرارات كثيرة (2026-06-09). **اقرأ هذا قبل أي تعديل على الستوري لتفادي إعادة الالتباس.**

**النموذج (مهم — متداخل لا مسطّح):**
- **حلقة واحدة لكل متجر مُشهَر** (`is_promoted=TRUE`)، وعند فتحها **شرائحه تُعرض ورا بعض داخلها** بأشرطة تقدّم (شريط لكل شريحة) ثم المتجر التالي. ❌ ليس «حلقة لكل شريحة» (جرّبناه ورُفض).
- المتاجر المكرّرة (نمشي، نمشي1..نمشي5) = صفوف master منفصلة = حلقات منفصلة (التفاف خاطئ من المستخدم؛ الصح متجر واحد بعدة شرائح).

**قاعدة البيانات:** جدول `story_slides` (migration 044): `id, master_id (FK→master ON DELETE CASCADE), media_url, sort_order, is_active, created_at`. عدة صفوف/متجر = عدة ستوري مستقلة. العمود القديم `master.story_media_url` **متقاعد** (migration 045 — لا يُكتب ولا يُقرأ؛ كان فخّ رفعات أثناء انتقال النشر). **لا مسح تلقائي للجدول** (لا تريغر/cron/auto-migration)؛ الحذف فقط بزر 🗑️ أو CASCADE من حذف المتجر.

**التحليلات:** `story_views` مفتاحها `store_id` → كل شرائح المتجر تتجمّع في «العمود الرئيسي» للمتجر؛ الترند يحسبها. مربوطة بـ [[users-analytics-rules]].

**الـ API:** `/coupons` يرجّع `story_slides: string[]` لكل متجر عبر subquery مرتبط ([api/routers/coupons.py](api/routers/coupons.py) `_select_lang_clause` الفرعين) + سكيمة `StoreResult.story_slides`.

**الداشبورد:** صفحة **«🎬 إضافة استوري»** ([dashboard.py](dashboard.py)) — اختر متجر → فعّل الإشهار (is_promoted) → أضف/احذف/رتّب شرائح متعددة. الرفع عبر `_upload_story_media` (Cloudinary `resource_type=auto`، public_id فريد بـ timestamp فلا يستبدل). شييك الإشهار أُزيل من فورم «إدخال الماستر».

**الواجهتان:**
- الويب: [components/StoreStories.tsx](dealpulseksa-web) (ريبو منفصل) — slideIndex متداخل، **createPortal لـ body** (z-[60]) للهروب من stacking context فوق الهيدر (sticky z-50)؛ نافذة الإبلاغ z-[70].
- الميني-ويب: `miniapp.html` (renderStorySlide/storyNext/startStoryTimer) — عارض z-500 (بلا هيدر يغطّيه).
- **الفيديو:** يكمّل مدّته الكاملة ثم ينتقل (لا مؤقّت 6 ثوانٍ)؛ الصورة/الشعار 6 ثوانٍ. **الصوت مُشغّل افتراضياً + زر كتم/تشغيل**. تحسين Cloudinary `f_auto,q_auto` + `poster` (so_0) لتحميل أسرع وبلا شاشة سوداء.

**نظام الطبقات الثلاث + الألوان (2026-06-12 — migration_052/053):** صف الستوري يُرتّب ويُلوّن بثلاث طبقات **مستقلّة بالحساب والأعداد** (لا تخلط بينها):
1. **ترند يومي** — حلقة برتقالية + نار برتقالية 🔥. العدد الافتراضي 3 (الأكثر نشاطاً 24 ساعة). يظهر **أولاً**.
2. **ترند أسبوعي** — حلقة زرقاء + نار زرقاء (نفس 🔥 + `hue-rotate(160deg)`). الافتراضي 7. يظهر **ثانياً**.
3. **عادي** — مُشهَر يدوياً بلون مخصّص من `master.story_ring_color` (gold/silver/bronze/red/green/purple/pink، NULL=تلقائي). يظهر **ثالثاً**. البرتقالي/الأزرق محجوزان للترند.
- **الترتيب**: يومي→أسبوعي→عادي (sort ثابت في StoreStories + renderStoryRow). قاعدة اللون: ترند يغلب لون العادي (متجر واحد = لون طبقة واحدة).
- **الأعداد قابلة للتحكّم** من «تحليل المتاجر → تفضيلات الترند»: `platform_settings.trend_daily_count` (0-3)، `trend_weekly_count` (0-7). **0 = إيقاف الطبقة**. تُقرأ في `trend.py._trend_counts` (الـAPI الحي) و`dashboard._sa_trend_store_ids`. التثبيت اليدوي عبر `trend_overrides` (rank ضمن العدد فقط — لا catch-all).
- **مدة/حذف تلقائي للشريحة:** `story_slides.expires_at` (timestamptz، NULL=دائم). الـAPI يستبعد المنتهية (`expires_at IS NULL OR > now()`). الداشبورد: حقل «يُحذف بعد N أيام» + زر «♾️ اجعلها دائمة» + نظرة عامة بكل المتاجر المُشهَرة/ذات الشرائح. الحذف = إخفاء فوري (الصف يبقى للحذف اليدوي).
- `story_ring_color` في `_select_lang_clause` و`_select_light_clause` (الميني يستخدم light) + `StoreResult`.

الـ migrations: 043 (عمود story_media_url — متقاعد لاحقاً)، 044 (جدول story_slides)، 045 (إنقاذ+تقاعد العمود القديم)، 052 (expires_at)، 053 (story_ring_color + أعداد الترند). مرتبط بـ [[railway-deployment]] و [[git-sync-workflow]] (ريبوان منفصلان).
