# Project Memory Index

> **كيف تُقرأ هذه الذاكرة:** ١٢٩ ملفاً / ~٥٣٣ KB. **الفهرس فقط هو ما يُحمَّل تلقائياً — المتون لا.**
> السطر هنا **عنوان، وليس الحقيقة**. الحقيقة في المتن.
> **الطبقة ٠ تُقرأ متونها قبل أي مهمة.** من بقية الطبقات: افتح ما يخصّ مهمتك، وأعلن ما فتحته.
> الحوائط الصلبة منسوخة نصّاً في `CLAUDE.md` — لا تعتمد على أن تفتح ملفاً لتعرف حائطاً.

---

## 🔴 الطبقة ٠ — اقرأ متونها قبل أي مهمة (١١)

- [🤝 Partnership Protocol](protocol_partnership.md) — ٨ أنماط بالاسم + دورة انضباط + طقوس جلسة + سياسة المصادر
- [No Philosophy — Just Execute](feedback_no_philosophy.md) — لا خيارات/تمهيد؛ ابدأ بالأوضح؛ سؤال نصّي واحد عند العجز
- [Treat User as Senior Engineer](feedback_senior_engineer.md) — خبير ٢٠+؛ لا فلسفة/خيارات/أساسيات؛ اقرأ حدّد نفّذ
- [🧱 No DB Writes Without Permission](feedback_no_db_writes_without_permission.md) — INSERT/UPDATE/DELETE يحتاج إذناً صريحاً؛ «يلا نبدا» ليس إذناً
- [🧱 Always Push, Never Leave Work Local](feedback_always_push.md) — أجهزة متعددة؛ push كل شيء، لا stash، pull بالبداية
- [🧱 SEO White-Hat Only](seo_white_hat_only.md) — White-Hat فقط؛ محرّك ببوابات؛ SEO_AUTO_PUBLISH على DEALPULSEKSA
- [🛡️ Content Guardrails Playbook](content_guardrails_playbook.md) — سلامة/YMYL + صفر فبركة + تنسيق + ربط داخلي + صراحة استراتيجية
- [🔓 Full Authority Granted](feedback_full_authority.md) — تفويض تنفيذ ذاتي على الأفعال المحلية القابلة للعكس (لا يبطل حوائط DB/الحذف)
- [🔓 Bot Freeze LIFTED](bot_frozen_lock.md) — البوت مفكوك ٢٠٢٦-٠٧-٠٧؛ التعديل ضمن البروتوكول؛ حوائط DB/الإنتاج باقية
- [Mirror Audit — Trace Not Claim](feedback_mirror_audit.md) — دقّق الـ agents ونفسك بالـ trace الخام؛ الأفضلية للأرقام
- [Git Sync Workflow](git_sync_workflow.md) — جهازان: pull قبل، push بعد كل تغيير؛ main = Railway prod

---

## ١) أسلوب العمل والتفضيلات (١٩)

- [User Preferences](user_preferences.md) — how the user likes to work
- [Analysis Style](feedback_analysis_style.md) — جداول مقارِنة تقود قراراً عبر كل المتاجر؛ أفعال وأكواد لا كلام ملمّع؛ أقفل الصفحة قبل التالية
- [Judge by Output](feedback_output_over_engineering.md) — يقيّم بالمخرَج لا صعوبة السباكة؛ اكشف سقف الأداة بصراحة
- [Regression Audit First](feedback_regression_audit.md) — «كان يشتغل قبل تغييرك» → افحص diffs الأخيرة أولاً؛ لا تغييرات تخمينية
- [Check .env First](feedback_check_env_first.md) — مشاكل config: اقرأ .env + endpoints أولاً ثم Railway
- [No Dead Code / No Premature Opt](feedback_no_dead_code.md) — كل سطر حقيقي موصول مبرّر ببوتلنك فعلي
- [Zero Friction Onboarding](feedback_zero_friction.md) — اجمع البيانات عند نقطة القيمة (action-gated) لا الدخول
- [Store Selection Criterion](feedback_store_selection.md) — معرفة السعودي+السياق تغلب العمولة؛ أبقِ المعروف احذف الغريب
- [Prefer Codes over Tracking Links](feedback_prefer_codes_over_tracking_links.md) — المالك يفضّل الأكواد لا روابط التتبّع (إسناد أنظف + الروابط تنحجب)
- [Never Publish Competing Codes](feedback_never_publish_competing_codes.md) — لا تذكر كود المتجر الترحيبي ولو كان أعلى
- [Always Publish When Done](feedback_always_publish.md) — auto commit+push عند الإنجاز؛ main=prod؛ لا تسأل
- [No Backticks in blog.ts Literals](feedback_no_backticks_in_template_literals.md) — ``` داخل body يكسر SWC؛ استخدم inline/-
- [AI Mastery Goal](user_ai_mastery_goal.md) — يريد برومبت عالمي معاد الاستخدام؛ مهتم بهندسة البرومبت؛ رأي خبير صريح
- [العقل المدبر — البروتوكول](protocol_mastermind.md) — نواة + انخراط (٠–٥ أسئلة) + ٤ أوضاع + ٤ نداءات
- [Mastermind Prompt](mastermind_prompt.md) — «العقل المدبر»: موقع الملف + سلوك التفعيل
- [Memory Sync via Junction](memory_sync_junction.md) — ذاكرة واحدة بالريبو + junction؛ تتزامن مع git؛ لا تفرّع
- [Skills Install Manifest](skills_install_manifest.md) — ٢٣٨ skill على user في ~/.claude/skills (٦ ريبوهات)
- [Marketing Skills Toolkit](marketing_skills_toolkit.md) — 17 skill تسويق؛ المخرجات عربي/سعودي + White-Hat
- [Reconcile Web Repo Separately](reconcile_web_repo_separately.md) — dealpulseksa-web ريبو مستقل؛ افحصه أولاً

## ٢) البنية والتشغيل والنشر (١٣)

- [Project Overview](project_overview.md) — DealPulse KSA: 3-component architecture, DB, Railway
- [Setup Guide](setup_guide.md) — run locally on a new machine (deps, env, migrations)
- [Bug Fixes Log](bug_fixes.md) — bugs fixed and why (don't reintroduce)
- [Railway Production Deployment](railway_deployment.md) — الخدمة الموحّدة، tag الرجوع، BotFather + مطبّات إرث
- [Railway Scheduler Worker](railway_scheduler_worker.md) — config منفصل، cron ≥5د، تخطّي healthcheck
- [Single Source of Truth](single_source_of_truth.md) — DB واحد + داشبورد واحد؛ .env على Railway فقط
- [Platform Monitoring](platform_monitoring.md) — «متابعة المنصة»: صفحة + ضوابط + تقرير صحة + أداء API
- [🔒 Security Hardening](security_hardening.md) — فحص أمني (صفر ثغرة حرجة)؛ CSP بـnext.config؛ /docs مقفول بالإنتاج
- [Bot Capacity & Scaling](bot_capacity_scaling.md) — سقف ~30/ث؛ 16 عامل/طابور 12k؛ مسار Redis/sharding
- [Completed Features Log](project_completed_features.md) — ميزات مبنيّة سابقاً (تسويق بريدي بمركز الإشعارات، إصلاح تحليل الموقع)
- [Email Infrastructure](project_email_infrastructure.md) — Resend مربوط بـdealpulseksa.com؛ noreply@؛ SMTP احتياطي
- [Weeks Roadmap](weeks_roadmap.md) — `weeks plan.txt` خطة المخطط أسبوع-بأسبوع (W1-4 done)
- [Entrepreneur Bootcamp](entrepreneur_bootcamp.md) — معسكر ٤ دورات (م. يوسف)؛ التسويق المتكامل ✅؛ نبض كـcase study

## ٣) قاعدة البيانات وموثوقية الأرقام (٩)

- [DB Foundation Audit](db_foundation_audit.md) — **لقطة حيّة ٢٠٢٦-٠٨-٠٥: ٧١ جدول / ٣٨ فارغ (٥٤٪) / master ٥٢**؛ العدّادات total_*؛ دَيْن النوع بلا contract
- [master.store_id Not Unique](db_master_duplicate_store_id.md) — «نون» مكرّر (8,21) يمنع UNIQUE/FK؛ dedupe pending
- [Local DB Detached from Prod](db_local_vs_railway.md) — localhost = dummy؛ الإنتاج عبر DATABASE_URL
- [Data Trust: Geo/Device](data_trust_geo_device.md) — bot_users.city/device مفبركة؛ المدينة الحقيقية من web_users/action_logs فقط
- [Users Analytics Rules](users_analytics_rules.md) — قواعد العدّ/الهوية/الجغرافيا لتحليل المستخدمين
- [Web Visits Tracking](web_visits_tracking.md) — web_visits (Migration 060) جلسة-مستوى؛ بوتات مفلترة
- [Unified Favorites](unified_favorites.md) — user_favorites SSOT + كتابة مزدوجة **حيّة** (ادّعاء «اختفت» كان غلطاً)؛ **الإزالة لا تُسجَّل** في action_logs
- [Bot-vs-Promo 3-Signal Check](bot_vs_promo_heuristic.md) — قبل اتّهام قفزة بالبوت: visitor_id + timing + ASN
- [Owned Audience Reality](owned_audience_reality.md) — ٥ مستخدمي بوت + ١٠ حسابات ويب + صفر بثّ؛ رهان تيليجرام بلا جمهور

## ٤) ميزات المنتج (١٠)

- [Trend System Architecture](trend_architecture_final.md) — ١٤ قرار: نوافذ/حشو/تداخل/تثبيتات/فلاتر ستوري/نقر/debounce
- [Trend Uses source='all'](trend_source_all.md) — DB واحد، ترند موحّد، لا تجزئة per-platform؛ البوت بلا ستوري
- [Story System Design](story_system_design.md) — story_slides؛ نموذج متداخل؛ فيديو+صوت؛ Cloudinary؛ web portal z-[60]
- [Support System](support_system.md) — دعم عبر Telegram Bot API (بلا قروبات/webhook)؛ support_tickets؛ migration 039
- [Publish Channels Feature](publish_channels_feature.md) — master.publish_channels لكل متجر؛ API channel؛ fallback «حصري بالموقع»
- [Season Reminders Feature](season_reminders_feature.md) — التقاط زائر /calendar بإيميل بلا تسجيل؛ مزلق `start` ≠ يوم الذروة
- [Calendar Conversion Hub](calendar_conversion_hub.md) — كل موسم صار بوابة (أزرار أقسام + دليل + عبارة فريدة)
- [Occasion Page Relevance Filter](occasion_page_relevance_filter.md) — store_tags تصنيف لا موسم؛ + master.occasions (migration_067)
- [Web Login Gate Model](web_login_gate_model.md) — الموقع مفتوح؛ الستوري/المفضلة للمسجّلين؛ حركات المجهول بـ visitor_id
- [Store Page Evergreen (404 Root Cause)](store_page_evergreen.md) — `last_time>=CURRENT_DATE` أخفى المتجر → 404؛ المتجر دائم والكوبون يُفرَّغ

## ٥) التحليلات وBI (٦)

- [Store Analytics BI Suite](store_analytics_bi.md) — «تحليل المتاجر» (4 تبويبات) + AI عبر Groq REST
- [Analysis Rebuild Strategy](analysis_rebuild_strategy.md) — إعادة بناء 6 صفحات تحليل؛ 3 مسارات دخل + zero-fakery
- [Store Analytics Final Structure](analytics_store_structure.md) — 6 أقسام + أعمدة + إجمالي؛ «أبرز» = top favorites
- [Windsor GSC Connector](windsor_gsc_connector.md) — الخطة المجانية ترجع صفوفاً وهمية بأصفار بلا خطأ
- [Google Keyword Planner](google_ads_keyword_planner.md) — Ads API بمحرك الفرص؛ MCC 857-047-5609؛ v21؛ Basic Access
- [Keyword Demand (KSA)](keyword_demand_ksa.md) — الطلب على البراندات الكبيرة (10K-100K)؛ متاجرك ~10-100؛ iHerb أسرع مكسب

## ٦) السيو (١٧)

- [SEO Indexation Status](seo_indexation_status.md) — الفهرسة 4→150؛ انفجار ظهور يوليو؛ العنق = المركز+CTR
- [SEO Deep Audit Fixes](seo_deep_audit_fixes.md) — بق light-AR 500 (is_trending BOOLEAN) أفرغ الخريطة صامتاً؛ اسحب الباك-إند أولاً
- [SEO Authority Building](seo_authority_building.md) — crawled-not-indexed سقف سلطة؛ باكلينكس White-Hat
- [SEO High-Demand Front](seo_high_demand_front_opened.md) — فخّ AR=draft+EN=noindex؛ نُشرت 23 صفحة؛ نون/نمشي محجوبان بالسلطة
- [SEO Page Portfolio Verdict](seo_page_portfolio_verdict.md) — ٧١٠/٧٦٤ صفحة صفر نقرة؛ المتاجر نيّة ميتة؛ التجميع وحده يكسب
- [SEO Category Query Alignment](seo_category_query_alignment.md) — ٣٨ صفحة قسم؛ الطلب «تخفيضات على/متاجر/عروض» لا «كوبونات»
- [SEO Meta Code: Per-Network](seo_meta_code_leak.md) — كشف الكود يتبع نموذج الإسناد (~٣٧ يُكشف / ~١١ يُحجب)؛ attribution.ts
- [SEO Google Indexing Live](seo_google_indexing_live.md) — Google Indexing API فُعِّل؛ ٢٠٠ صفحة/يوم
- [SEO Bulk Reindex Ops](seo_bulk_reindex_ops.md) — reindex-urls؛ Cloudflare ≤25 URL/نداء؛ IndexNow بلا حصة
- [SEO AI Visibility Opt-In](seo_ai_visibility_optin.md) — robots opt-in لـ15 كراولر AI + llms.txt مُثرى
- [SEO Owned-Channels Pivot](seo_owned_channels_pivot.md) — رفض Reddit/Quora/مدوّنين؛ التركيز على X+Telegram+IG المملوكة
- [SEO PR Blitz Kit](seo_pr_blitz_kit.md) — seo/pr_blitz_kit.md لترويج /calendar
- [Domain Authority Plan](domain_authority_plan.md) — White-Hat؛ الربط الداخلي منجز؛ المتبقّي عناقيد/Schema/باكلينك
- [Domain Canonical Trap](domain_canonical_trap.md) — الصح dealpulseksa.com؛ dealpulesksa.com ميّت؛ احسم بـcurl
- [Content/Programmatic Strategy](content_programmatic_strategy.md) — «عربي فقط لا /en»؛ category-content + هَب أقسام؛ لا صفحات رقيقة
- [Seasonal School Traffic Bridge](seasonal_school_traffic_bridge.md) — عنقود المدرسة يجرّ سعوديين موسمياً؛ الجسر ١٣ رابط
- [Competitor Landscape](competitor_landscape.md) — الموفّر القائد؛ الفجوات: تحقّق/تيليجرام/نيش محلي/AEO

## ٧) الموقع — dealpulseksa-web (٥)

- [Website Project](website_project.md) — Next.js repo، Firebase project، deployment checklist
- [Website Design Preferences](website_design_preferences.md) — Apple-style، watermark، Firebase OTP
- [Website SEO Engine](website_seo_engine.md) — lib/seo، BILINGUAL_ENABLED، revalidate/indexnow، env
- [Web Repo Verification Recipes](web_repo_verification_recipes.md) — tsconfig ضيّق يتجاوز OOM؛ لا عربية داخل .ps1
- [Web Blog OOM + Client-Prop](web_blog_monolith_oom_and_client_prop_serialization.md) — قصّ related لصفحة >2MB؛ next dev يـOOM على blog.ts

## ٨) المحتوى والمدوّنة (٢٠)

- [Voice Bible](voice_bible.md) — نموذج الصوت التحريري (عيّنة فيتامين د مشرَّحة)؛ قلّد العيّنة
- [Blog Total = Count It Live](blog_massive_content_session.md) — ٦٥٠ مقال حيّ؛ **عُدّ بـ`grep -cE "^\s*slug:" lib/blog.ts`** لا تجمع تقديرياً
- [Health Content Cluster](health_content_cluster.md) — 10 مقالات مكمّلات iHerb؛ كود QQC1568؛ معايير الكتابة
- [Health Citation Sourcing](health_citation_sourcing.md) — Mayo/NIH يحجبان الـcrawlers (403 إيجابي كاذب)؛ استخدم Harvard Nutrition
- [Blog Internal-Link De-orphan](blog_internal_link_deorphan.md) — 65 مقال يتيم صُفِّرت؛ top-6 getRelatedPosts يجوّع الذيل
- [Blog Inline Code Chips](blog_inline_code_chips.md) — شارة كود/CTA بجانب كل ذكر متجر في ١٣٦٥ مقال؛ العلاج بالعارض
- [Jolina Pre-Purchase Angle](jolina_prepurchase_angle.md) — الزاوية «الاسترجاع/الرسوم» لا الكود؛ مواقع JS لا تُقرأ بـcurl
- [Blog AliExpress Cluster](blog_aliexpress_cluster.md) — 150 مقال قطع سيارات؛ توصية تنقية+noindex
- [Blog 14 Clusters July 11](blog_14clusters_july11.md) — 280 مقال (14 متجر) ربط شبكي متبادل
- [Blog 7 Clusters July 11](blog_7clusters_july11.md) — 105 مقال (عود رويال + قطرة عسل + 5 عبايات)
- [Blog Home Furniture Cluster](blog_home_furniture_cluster.md) — أثاث ١٩ مقال (٦ أقسام)؛ web 97a1c5a
- [Blog Toys Cluster](blog_toys_cluster_progress.md) — ألعاب مستهدَف ٧٢؛ منجَز ١٠/٧٢؛ باقي ٦٢ بأولويات
- [Blog The Deal Cluster](blog_thedeal_cluster.md) — ذا ديل أوتلت 15؛ web 90935f8
- [Blog VogaCloset Cluster](blog_vogacloset_cluster.md) — فوغا كلوسيت 15 + ربط متبادل مع ذا ديل
- [Blog Mamas & Papas Cluster](blog_mamaspapas_cluster.md) — ماماز 15 (سلامة صارمة) + ربط ثلاثي
- [Blog H&M Cluster](blog_hm_cluster.md) — اتش اند ام 15 (يستحقّ/لا يستحقّ) + ربط رباعي
- [Blog Bedinroom Cluster](blog_bedinroom_cluster.md) — بيد إن روم 14 (سفر/فنادق)؛ المتجر master id=55 حيّ
- [Blog Coffee Moments Cluster](blog_lahazat_cluster.md) — لحظات القهوة 15 + ربط من الهَبين
- [Blog Jana Al-Asal Cluster](blog_jana_honey_cluster.md) — جنى العسل 15 (YMYL) + إصلاح مرجع مكسور
- [Blog ASQ Cluster](blog_asq_cluster.md) — عبدالصمد القرشي ١٢ مقالاً؛ الاسم بلا مسافة؛ تحقّق esbuild

## ٩) قنوات الأفلييت والشراكات (١٢)

- [Salla Affiliate Channel](salla_affiliate_channel.md) — قناة محلية (خصم+عمولة بلا بوّابة)؛ منتقياً؛ ✅ قُبلت
- [Salla Orders = Code Attribution](salla_orders_attribution_reality.md) — سلة تنسب بالكود لا النقرة؛ ثغرة تتبّع النسخ اليدوي
- [Salla Proven Converters](salla_proven_converters.md) — أول ١٣ طلب (~٥٢٥ ر.س)؛ هدف ٢٠٪ الأعلى (وُصل web b957858)
- [Admitad Affiliate Setup](admitad_affiliate_setup.md) — مساحتان؛ بوّابتان (نوع الترافيك+حجم الجمهور)؛ ابدأ بالسهل
- [Admitad DNS Block](admitad_dns_block.md) — ISP يحجب admitad.com (NXDOMAIN مزوّر)؛ الحل DNS مشفّر
- [CodeMap Affiliate Channel](codemap_affiliate_channel.md) — كوبونات فقط بلا تتبّع؛ براندات كبيرة؛ تكمّل سلة
- [Boostiny Publisher Channel](boostiny_publisher_channel.md) — ناشر Boostiny (عملاء كبار/توصيل طعام)؛ الطلب مُقدَّم
- [DCM Network Channel](dcm_network_channel.md) — ٣ منصّات؛ ندرة أكواد أقفلت الحساب؛ ليس رافعة نمو
- [Zid Affiliate Channel](zid_affiliate_channel.md) — سفير زد: عمولة 30%/خصم 20%، إسناد بالرابط فقط
- [Jahez Direct BD](jahez_direct_bd.md) — تواصل مباشر بلا شبكة؛ البريد من زيارة المقر؛ مسوّدة في outreach/
- [Affiliate PPC Brand Restrictions](affiliate_ppc_brand_restrictions.md) — منع المزايدة المدفوعة على البراند؛ SEO عضوي مسموح
- [Contact Emails](contact_emails.md) — الصح `dealpulseksa@gmail.com`؛ `dealpules` خطأ مثبّت بالكود؛ + إيميل DCM

## ١٠) التسويق والسوشيال (٧)

- [Marketing Baseline & Strategy](marketing_baseline_and_strategy.md) — ~121 سعودي/شهر (89% بوتات)؛ العنق الترافيك لا التحويل
- [Instagram Content Engine](instagram_content_engine.md) — ريلز Dark Luxe؛ @dealpulseksa؛ «الحساب ميت» = الصيغة غلط لا shadow-ban
- [Instagram Growth Engine](ig_growth_engine.md) — caption SEO + auto-publish + /ig bio + keyword bank
- [IG Publishing Policy](ig_publish_policy.md) — الستوري التلقائية ملغاة؛ الريل كل 6 بثّات
- [Brand Face for Flow Reels](brand_face_reels.md) — بنت خضراء سعودية (brand_face_crop.png)؛ نطق «نبض الصفقات»
- [Social Listening Deferred](social_listening_deferred.md) — الرصد الاجتماعي/رادار الصفقات مؤجَّلان (مصادر ميتة)
- [Local TTS — XTTS v2 (REMOVED)](tts_engine_xtts_v2.md) — بُني وحُذف؛ عربي محلي ضعيف؛ الطريق API عصبي مدفوع

---

### صيانة الفهرس

**كل ملف على القرص يجب أن يظهر هنا.** ملف خارج الفهرس = ذاكرة غير مرئية (حدث فعلياً: ٤ ملفات كانت مفقودة حتى ٢٠٢٦-٠٨-٠٥، منها [feedback_analysis_style.md](feedback_analysis_style.md)). للتدقيق:

```powershell
$idx=(Get-Content Claude_Memory\MEMORY.md -Encoding UTF8|%{if($_ -match '\(([^)]+\.md)\)'){$matches[1]}})
(Get-ChildItem Claude_Memory -Filter *.md|?{$_.Name -ne 'MEMORY.md'}).Name|?{$idx -notcontains $_}
```
