---
name: publish_channels_feature
description: per-store channel targeting (master.publish_channels) for affiliate compliance — website/bot/social
metadata: 
  node_type: memory
  type: project
  originSessionId: b982bbc2-2107-4339-a759-ee4be1b52729
---

ميزة **استهداف القنوات لكل متجر** (شُحنت 2026-06-15، commit 67b64a4). تحلّ تعارض شروط الأفلييت: معلنون يمنعون Telegram (SHEIN/Airalo)، فنُخفي المتجر عن البوت ونبقيه على الموقع.

**العمود:** `master.publish_channels text` (migration_056). نص مفصول بفواصل من {`website,bot,instagram,threads,facebook`}. `bot` = البوت + الميني-ويب (واجهة واحدة). **NULL = كل القنوات** (توافق المتاجر القديمة)؛ `''` = مخفي عن الكل.

**التحكّم:** نموذج الماستر في dashboard.py (ADD + EDIT) فيه multiselect «📤 إرسال إلى» (ثابت `PUBLISH_CHANNELS`، افتراضي = الكل).

**آلية الفلترة (مفاتيح متمايزة فلا تصادم في ILIKE):**
- API `api/routers/coupons.py`: بارامتر `channel` (افتراضي `website`) على list/search/detail/by-slug/top-favorited؛ الشرط `publish_channels IS NULL OR publish_channels ILIKE %(chpat)s`. الموقع (Next.js) لا يمرّر channel → website تلقائياً (بلا تعديل للويب).
- الميني-ويب (miniapp.html) يمرّر `channel=bot`.
- البوت (deal_pulse_bot.py، **تعديل مأذون لمرة على الملف المجمّد** [[bot_frozen_lock]]): fetch_api_results يمرّر channel=bot؛ _db_search/listings/favorites تفلتر `ILIKE '%bot%'`؛ + fallback جديد `_db_search_website_exclusive` → البحث عن متجر حصري للموقع يردّ زر «حصري بالموقع» برابط `WEBSITE_URL/store/{store_id}`.
- محرّك SEO `api/seo/auto_pipeline.py`: التوليد اليومي 3ص يقتصر على متاجر `website` (SEO عضوي ≠ brand bidding المدفوع المحظور). يرتبط بـ[[seo_white_hat_only]] و[[admitad_affiliate_setup]].

**قنوات السوشيال موصولة بالنشر** (2026-06-15): القائمة صار فيها `telegram`(📣 قناة) + `discord` (إضافةً لـ instagram/threads/facebook). `api/social/dispatcher.py` يحترم publish_channels: المنصات المُدارة `_MANAGED_SOCIAL={telegram,discord,instagram,threads,facebook}` تُنشَر فقط لو معلَّمة (NULL=الكل)؛ غير المُدارة (x/pinterest/linkedin) تُنشَر حسب التهيئة. سجل النشر = `social_posts_log`. ملاحظة: المتاجر المحفوظة قبل هذا (AliExpress=website,bot,instagram,threads,facebook) لازم تُعدَّل وتُعلَّم telegram/discord لتُنشَر لها. حالة المنصات: threads/telegram/discord/fb/ig=sent، x=failed(CreditsDepleted)، linkedin/pinterest=not configured.

**سماح/منع SEO لكل متجر** (migration_057، عمود `master.seo_enabled boolean default true`): بعض المعلنين يمنعون SEO على اسم البراند صراحةً (AliExpress/Alibaba group: حظر+عدم دفع، عكس Trip.com/SHEIN حيث العضوي مسموح). خانة «🔎 السماح بتوليد SEO» في نموذج الماستر (ADD+EDIT)؛ select_top_demand_stores يضيف `AND COALESCE(seo_enabled,TRUE)=TRUE`. FALSE = استثناء كامل من SEO. حلّ بديل أنظف من blocklist الكلمات.
