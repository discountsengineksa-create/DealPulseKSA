---
name: unified-favorites
description: Unified cross-platform favorites system (user_favorites table) + deferred notifications phase
metadata: 
  node_type: memory
  type: project
  originSessionId: 1a67bb99-b093-4ec1-a192-c0131fd281b9
---

نظام المفضلة الموحّد (wave منفّذ 2026-05-31، commit `1bca207` backend + `a2c38d5` web).

**القرار المعماري:** جدول `user_favorites` مُطبّع = مصدر الحقيقة الوحيد (SSOT) للتحليل والتنبيهات.

**🔴 تصحيحُ التصحيح (مُتحقَّق بالكود 2026-08-05): «الكتابة المزدوجة اختفت» كان ادّعاءً خاطئاً.**
النسخة السابقة من هذا السطر قالت إن `grep "(INSERT|UPDATE|DELETE).*manual_favorites"` = صفر.
**غلط** — البوت يكتبها في موضعين:
- `deal_pulse_bot.py:2051` `_add_favorite_db` → `INSERT INTO user_favorites` **ثم** تحديث `bot_users.manual_favorites` (السطر ~2065).
- `deal_pulse_bot.py:2089` `_remove_favorite_db` → `DELETE FROM user_favorites` **ثم** `UPDATE bot_users SET manual_favorites = array_remove(...)` (السطر 2100).

الكتابة المزدوجة **حيّة**: `user_favorites` = SSOT، و`manual_favorites` = cache متزامن.
درس: الـgrep الذي أنتج الادّعاء الخاطئ إمّا لم يشمل `deal_pulse_bot.py` أو قُرئ نتيجته بتسرّع.
**النمط الخطر: «تحقّقتُ» بلا لصق مخرَج الأمر = ادّعاء لا تحقّق.** → [[feedback_mirror_audit]]

**⚠️ ثغرة حقيقية مكتشَفة أثناء التحقّق — الإزالة لا تُسجَّل:**
`handle_favorite_toggle` (`deal_pulse_bot.py:2220`) يستدعي `log_action(..., 'favorite_add', ...)`
عند **الإضافة فقط** (سطر 2233). عند الإزالة (سطر 2228) لا يُسجَّل أي حدث، و`_remove_favorite_db`
لا يسجّل داخلياً. **النتيجة:** `action_logs` يرى الإضافات ولا يرى الإزالات، فأي تحليل «تسرّب
المفضّلة» أعمى. هذا يفسّر ما بدا شذوذاً في ٢٠٢٦-٠٨-٠٥: حدث `favorite_add` واحد (٢٠٢٦-٠٦-٢٤)
بينما `user_favorites` **و**`manual_favorites` فارغان — أُضيف ثم أُزيل، والإزالة لم تُسجَّل.
**لا بق في الكتابة المزدوجة.** الإصلاح (لو أراده المالك): `log_action(store_id, 'favorite_remove', ...)`
في فرع الإزالة. → [[db_foundation_audit]]

**الجدول:** `platform('bot'|'web'|'miniapp')` + (`web_user_id` أو `telegram_id`، CHECK مالك واحد
بالضبط) + `store_id` (بلا FK لـ master لأنه غير فريد) + `created_at` + `last_notified_at`.
partial-unique على كل مسار هوية. البوت والميني-ويب يشتركان في `telegram_id` فالشخص الواحد
صف واحد لكل متجر.

**الأسطح:** البوت (زر صريح `fav:{sid}` + قائمة «❤️ مفضلتي» `nav:favs`)، الميني-ويب
(`/users/telegram-favorites[/list]` بمصادقة initData، قلب سيرفري بدل localStorage)، الموقع
(`lib/favorites-context.tsx` FavoritesProvider + قلب على كل StoreCard وStoreDetail)، الداشبورد
(تبويب «❤️ المفضلة» في «تحليل المتاجر»: leaderboard + توزيع المنصات + «مين فضّل متجراً» +
عمود «❤️ مفضّلون» في لوحة القرار الرئيسية).

**migration_028 — مفضلة الأقسام (polymorphic، أضافها المالك على جهازه الثاني):**
`user_favorites` صار polymorphic عبر `kind('store'|'category')` + `category_name`، `store_id`
صار nullable، CHECK `uf_kind_target_consistent` يضمن نوع واحد متّسق، indexes منفصلة per-kind.
السبب: استعلام push واحد مستقبلاً («كود جديد لمتجر X قسمه أزياء ⇒ نبّه من فضّل X أو فضّل أزياء»).
**مهم:** `_sa_load_favorites()` صار يرجّع الصفّين، فأي تحليل متاجر **يجب** أن يفلتر
`kind=='store'` وأي تحليل أقسام `kind=='category'`. مفضلة الأقسام مدمجة في «تحليل الأقسام»
(6 تبويبات: عمود مفضّلون + بطاقة القسم «مين فضّل» + تبويب «الأكثر تفضيلاً»).

**المصفوفة (2026-06-01) — التفاعل موجود في كل الأسطح للنوعين:** البوت (`fav:`+`cfav:`)،
الميني-ويب (`toggleFav`+`toggleCatFav`)، **والموقع كذلك مكتمل** — المالك نفّذ مفضلة الأقسام
في الموقع (`components/CategoryTileFav.tsx`, `CategoryFavButton.tsx`, hook `@/lib/favorites`
بـ `storeIds/categories/toggleStore/toggleCategory/isCategoryFav`). **تنبيه: الموقع يستخدم
`@/lib/favorites` (هوك المالك) وليس `@/lib/favorites-context` الذي بنيتُه أنا في الموجة الأولى —
نسخته استُبدلت.**

**تحليل المستخدمين (الفحص الفردي):** أضفتُ تجميع مفضلة الشخص **منفصلة لكل حساب** (ويب ≠ تيليجرام)
ومنفصلة متاجر/أقسام (commit 5deb1f9). + عمود «❤️ مفضّلون» في لوحة قرار «تحليل المتاجر» (5541d6c).

**درس git مهم:** اسحب (pull) **كل** الريبوهات قبل التدقيق/العمل — لا تدقّق على نسخة محلية قديمة.
في 2026-06-01 دقّقتُ الموقع على local متأخّر فظننتُ مفضلة الأقسام ناقصة وأعدتُ بناءها = تكرار اتشال.
راجع [[git_sync_workflow]].

**تسمية المصادر في الداشبورد (قرار المالك 2026-06-02، commit 8d246d0):** البوت والميني-ويب
**نفس عائلة تيليجرام**، فلا يصح تسمية البوت «تيليجرام» والميني «ميني ويب» (تختلط بصرياً بـ«ويب»).
التسمية الموحّدة عبر كل الداشبورد: `bot`→**«📱 بوت»** · `miniapp/telegram_miniapp`→**«🔹 بوت - ميني»**
· `web`→**«🌐 ويب»**. تُعرَّف في `CHAN_MAP` + `SRC_FILTER`/`PLAT_FILTER` + خيارات `st.radio("المصدر")`
+ مقارنات `src_choice ==` — كلها نفس السلسلة الحرفية فالاستبدال الشامل يبقيها متناسقة. (بيانات
عمود `platform` نفسها صحيحة — تم التحقق: كل منصة تطابق نوع المالك، صفر تطابق خاطئ.)

**قاعدة تحليل المفضلة (قرار المالك 2026-06-01):** المفضلة **مِلك الشخص لا منصّة الإضافة**.
البوت + الميني-ويب = **حساب تيليجرام واحد** (نفس telegram_id) — **لا تفصل بينهما** ولا تُخفِ مفضلة
حسب فلتر المصدر. في جدول «مين نسخ» عمود «❤️ المفضلة» يُطابق بـ (identity + store_id) فقط ويعرض
**اسم المتجر** المفضّل («❤️ نمشي5») أو «—» — صادق في كل الفلاتر، مرة واحدة لكل صف في «الكل».
الويب حساب منفصل يتمايز بهويته. (غلطتُ مرتين: عرضتُ المنصة بدل الاسم، ثم فلترتُ بمنصة الإضافة
فأخفيتُ مفضلات — كلاهما خطأ. عمود `platform` يحفظ مصدر آخر إضافة فقط، لا يُستخدم للإخفاء.)

**مرحلة لاحقة مؤجّلة (بطلب المالك):** إرسال التنبيهات الفعلي «نزل كوبون/خصم جديد لمتجرك
المفضل». الأساس جاهز (`last_notified_at`). يحتاج: رصد الكوبونات الجديدة + dispatcher بوت/إيميل
+ ضوابط إرسال. لا تاريخ محدّد بعد. مرتبط بهدف [[user_ai_mastery_goal]] (التخصيص: كل شخص يحس
الموقع مصمّم له). راجع [[store_analytics_bi]] و[[analysis_rebuild_strategy]].
