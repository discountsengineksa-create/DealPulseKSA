# Project Memory Index

> ١٥١ ملفاً (عُدّت ٢٠٢٦-٠٨-٢٧ بعد ملفَّي كوكي الجلسة وصفّ الاهتمامات — `ls *.md | grep -v MEMORY.md | wc -l` = ١٤٩). **العدّ للمتون، بلا `MEMORY.md` نفسه** (`ls *.md` يعطي ١٤٩ — لا تنسخه هنا). **الفهرس وحده يُحمَّل — المتون لا.** السطر هنا **عنوان لا حقيقة**؛ الحقيقة في المتن.
> **الطبقة ٠ تُقرأ متونها قبل أي مهمة.** من الباقي: افتح ما يخصّ مهمتك وأعلن ما فتحته.
> الحوائط الصلبة منسوخة نصّاً في `CLAUDE.md`. سطرٌ بعدّة روابط = ملفات مستقلة جُمعت للاختصار.

## 🔴 الطبقة ٠ — اقرأ متونها قبل أي مهمة (١٢)

- [🤝 Partnership Protocol](protocol_partnership.md) — ٨ أنماط بالاسم + دورة انضباط + طقوس جلسة + سياسة المصادر
- [No Philosophy — Just Execute](feedback_no_philosophy.md) — لا خيارات/تمهيد؛ ابدأ بالأوضح؛ سؤال نصّي واحد عند العجز
- [Treat User as Senior Engineer](feedback_senior_engineer.md) — خبير ٢٠+؛ لا فلسفة/خيارات/أساسيات؛ اقرأ حدّد نفّذ
- [🧱 No DB Writes Without Permission](feedback_no_db_writes_without_permission.md) — INSERT/UPDATE/DELETE يحتاج إذناً صريحاً؛ «يلا نبدا» ليس إذناً
- [🧱 لا حذف من الكتالوج ولا من المدوّنة](feedback_never_delete_catalog_or_content.md) — متجر/مقال لا يُحذف إلا بطلب شخصي؛ التوصية مسموحة والتنفيذ ممنوع
- [🧱 Always Push, Never Leave Work Local](feedback_always_push.md) — أجهزة متعددة؛ push كل شيء، لا stash، pull بالبداية
- [🧱 SEO White-Hat Only](seo_white_hat_only.md) — White-Hat فقط؛ محرّك ببوابات؛ SEO_AUTO_PUBLISH على DEALPULSEKSA
- [🛡️ Content Guardrails Playbook](content_guardrails_playbook.md) — سلامة/YMYL + صفر فبركة + تنسيق + ربط داخلي + صراحة استراتيجية
- [🔓 Full Authority Granted](feedback_full_authority.md) — تفويض ذاتي على الأفعال المحلية القابلة للعكس (لا يبطل حوائط DB/الحذف)
- [🔓 Bot Freeze LIFTED](bot_frozen_lock.md) — البوت مفكوك ٢٠٢٦-٠٧-٠٧ ضمن البروتوكول؛ حوائط DB/الإنتاج باقية
- [Mirror Audit — Trace Not Claim](feedback_mirror_audit.md) — دقّق الـagents ونفسك بالـtrace الخام؛ الأفضلية للأرقام
- [Git Sync Workflow](git_sync_workflow.md) — جهازان: pull قبل، push بعد كل تغيير؛ main = Railway prod

## ١) أسلوب العمل والتفضيلات (٢١)

- [🔥 ضبط حرق التوكنز](feedback_token_burn_control.md) — تكلفة الدور = المحادثة كلها (قِيس ٦١٬٧٦٦ → ٨٥٥٬٣٥٦)؛ الصور تسكن السياق للأبد؛ العدّاد في statusline
- [User Preferences](user_preferences.md) — how the user likes to work
- [Analysis Style](feedback_analysis_style.md) — جداول مقارِنة تقود قراراً؛ أفعال وأكواد لا كلام ملمّع؛ أقفل الصفحة قبل التالية
- [Judge by Output](feedback_output_over_engineering.md) — يقيّم بالمخرَج لا صعوبة السباكة؛ اكشف سقف الأداة بصراحة
- [Regression Audit First](feedback_regression_audit.md) — «كان يشتغل قبل تغييرك» → افحص diffs الأخيرة أولاً؛ لا تغييرات تخمينية
- [Check .env First](feedback_check_env_first.md) — مشاكل config: اقرأ .env + endpoints أولاً ثم Railway
- [No Dead Code / No Premature Opt](feedback_no_dead_code.md) — كل سطر حقيقي موصول مبرّر ببوتلنك فعلي
- [Zero Friction Onboarding](feedback_zero_friction.md) — اجمع البيانات عند نقطة القيمة (action-gated) لا الدخول
- [Store Selection Criterion](feedback_store_selection.md) — معرفة السعودي+السياق تغلب العمولة؛ أبقِ المعروف احذف الغريب
- [Prefer Codes over Tracking Links](feedback_prefer_codes_over_tracking_links.md) — الأكواد لا روابط التتبّع (إسناد أنظف + الروابط تنحجب)
- [Never Publish Competing Codes](feedback_never_publish_competing_codes.md) — لا تذكر كود المتجر الترحيبي ولو كان أعلى
- [Always Publish When Done](feedback_always_publish.md) — auto commit+push عند الإنجاز؛ main=prod؛ لا تسأل
- [No Backticks in blog.ts Literals](feedback_no_backticks_in_template_literals.md) — ``` داخل body يكسر SWC؛ استخدم inline/-
- [AI Mastery Goal](user_ai_mastery_goal.md) — يريد برومبت عالمي معاد الاستخدام؛ مهتم بهندسة البرومبت؛ رأي خبير صريح
- العقل المدبر: [البروتوكول](protocol_mastermind.md) (نواة + انخراط ٠–٥ أسئلة + ٤ أوضاع + ٤ نداءات) · [البرومبت](mastermind_prompt.md) (موقع الملف + التفعيل)
- [Memory Sync via Junction](memory_sync_junction.md) — ذاكرة واحدة بالريبو + junction؛ تتزامن مع git؛ لا تفرّع
- [☁️ Claude Code Cloud Sessions](claude_code_cloud_sessions.md) — claude.ai/code + الجوال مربوطان بالريبو (٢٠٢٦-٠٨-٠٩)؛ يرثان الذاكرة، **لكن بلا `.env` فلا وصول لقاعدة البيانات**
- المهارات: [المثبَّتة](skills_install_manifest.md) (**٢٩٦ skill + ٢٥ أمراً على `Users\PC` بعد موجتَي ٢٠٢٦-٠٨-١١؛ الحمولة خارج `skills\` وإلا مهارات مكسورة صامتة؛ لا مهارة RTL/عربية على GitHub — total=0**) · [عدّة التسويق](marketing_skills_toolkit.md) (١٧ skill تسويق؛ عربي سعودي + White-Hat)
- [Reconcile Web Repo Separately](reconcile_web_repo_separately.md) — dealpulseksa-web ريبو مستقل؛ افحصه أولاً

## ٢) البنية والتشغيل والنشر والموقع (١٩)

- [Project Overview](project_overview.md) — DealPulse KSA: 3-component architecture, DB, Railway
- [Setup Guide](setup_guide.md) — run locally on a new machine (deps, env, migrations)
- [Bug Fixes Log](bug_fixes.md) — bugs fixed and why (don't reintroduce)
- Railway: [النشر](railway_deployment.md) (الخدمة الموحّدة، tag الرجوع، BotFather) · [عامل الجدولة](railway_scheduler_worker.md) (config منفصل، cron ≥5د، تخطّي healthcheck)
- [Single Source of Truth](single_source_of_truth.md) — DB واحد + داشبورد واحد؛ .env على Railway فقط
- [Platform Monitoring](platform_monitoring.md) — «متابعة المنصة»: صفحة + ضوابط + تقرير صحة + أداء API
- [🔒 Security Hardening](security_hardening.md) — فحص أمني (صفر ثغرة حرجة)؛ CSP بـnext.config؛ /docs مقفول بالإنتاج
- [Bot Capacity & Scaling](bot_capacity_scaling.md) — سقف ~30/ث؛ 16 عامل/طابور 12k؛ مسار Redis/sharding
- [Completed Features Log](project_completed_features.md) — ميزات مبنيّة سابقاً (تسويق بريدي، إصلاح تحليل الموقع)
- [Email Infrastructure](project_email_infrastructure.md) — Resend مربوط بـdealpulseksa.com؛ noreply@؛ SMTP احتياطي
- [Weeks Roadmap](weeks_roadmap.md) — `weeks plan.txt` خطة أسبوع-بأسبوع (W1-4 done)
- [Entrepreneur Bootcamp](entrepreneur_bootcamp.md) — معسكر ٤ دورات (م. يوسف)؛ نبض كـcase study
- الموقع: [المشروع](website_project.md) (Next.js + Firebase + checklist) · [التصميم](website_design_preferences.md) (Apple-style، watermark، OTP) · [محرّك السيو](website_seo_engine.md) (lib/seo، BILINGUAL_ENABLED، revalidate/indexnow)
- [Web Repo Verification Recipes](web_repo_verification_recipes.md) — tsconfig ضيّق يتجاوز OOM؛ اختبر clampTitle بالوسوم الحقيقية؛ لا عربية داخل .ps1
- [Web Blog OOM + Client-Prop](web_blog_monolith_oom_and_client_prop_serialization.md) — قصّ related لصفحة >2MB؛ next dev يـOOM على blog.ts
- [🎟️ Coupon Visual Identity](web_coupon_visual_identity.md) — التذكرة نُشرت ٢٠٢٦-٠٨-١١؛ **`view=light` يرجّع الكود/الرابط `null`** و**`StoreCard` ليست بطاقة الرئيسية**؛ الترند وُصل بالكتالوج
- [🎫 Logo: Ticket + DP](brand_logo_ticket_2026_08.md) — اللوقو الجديد اعتُمد ٢٠٢٦-٠٨-١٢ + طقم ٨٧ ملفاً بـ`Desktop\dpk-logo\KIT`؛ **الفافيكون الحالي ١٦×٨ بكسل**؛ وشبكة عيّنات خشنة أنتجت عيباً وهمياً
- [🎨 الهوية طُبِّقت على الأسطح الأربعة](brand_identity_applied.md) — `brand.py` + `style.css` مصدر الحقيقة؛ **ملفّات الخط `-ar` مجزّأة (٦٨١ محرفاً) فطبعت مربّعات**؛ وثغرة أحمر داكن في الدليل؛ وما تُرك عمداً

## ٣) قاعدة البيانات وموثوقية الأرقام (٩)

- [DB Foundation Audit](db_foundation_audit.md) — **حيّ ٢٠٢٦-٠٨-٠٥: ٧١ جدول / ٣٨ فارغ (٥٤٪) / master ٥٢**؛ العدّادات total_*؛ دَيْن النوع بلا contract
- [master.store_id غير فريد](db_master_duplicate_store_id.md) («نون» مكرّر 8,21 يمنع UNIQUE/FK) · [المحلي منفصل عن الإنتاج](db_local_vs_railway.md) (localhost = dummy؛ الإنتاج بـDATABASE_URL)
- [Data Trust: Geo/Device](data_trust_geo_device.md) — bot_users.city/device مفبركة؛ المدينة الحقيقية من web_users/action_logs فقط
- [Users Analytics Rules](users_analytics_rules.md) — قواعد العدّ/الهوية/الجغرافيا لتحليل المستخدمين
- [Web Visits Tracking](web_visits_tracking.md) — web_visits (Migration 060) جلسة-مستوى؛ بوتات مفلترة
- [Unified Favorites](unified_favorites.md) — user_favorites SSOT + كتابة مزدوجة **حيّة**؛ **الإزالة لا تُسجَّل** في action_logs
- [Bot-vs-Promo 3-Signal Check](bot_vs_promo_heuristic.md) — قبل اتّهام قفزة بالبوت: visitor_id + timing + ASN
- [Owned Audience Reality](owned_audience_reality.md) — ٥ مستخدمي بوت + ١٠ حسابات ويب + صفر بثّ؛ رهان تيليجرام بلا جمهور — **+ ٠٨-١٥: لا تقرير أداء لشريك أبداً، وكل ريال جاء من توزيع المالك لا الموقع، وطبقة الأدلة استُهلكت بـ٤ روابط**

## ٤) ميزات المنتج (١٠)

- [Trend System Architecture](trend_architecture_final.md) — ١٤ قرار: نوافذ/حشو/تداخل/تثبيتات/فلاتر ستوري/نقر/debounce
- [Trend Uses source='all'](trend_source_all.md) — DB واحد، ترند موحّد، لا تجزئة per-platform؛ البوت بلا ستوري
- [Story System Design](story_system_design.md) — story_slides؛ نموذج متداخل؛ فيديو+صوت؛ Cloudinary؛ web portal z-[60]
- [Support System](support_system.md) — دعم عبر Telegram Bot API (بلا قروبات/webhook)؛ support_tickets؛ migration 039
- [Publish Channels Feature](publish_channels_feature.md) — master.publish_channels لكل متجر؛ API channel؛ fallback «حصري بالموقع»
- [Season Reminders Feature](season_reminders_feature.md) — التقاط زائر /calendar بإيميل بلا تسجيل؛ مزلق `start` ≠ يوم الذروة
- [Calendar Conversion Hub](calendar_conversion_hub.md) — كل موسم صار بوابة (أزرار أقسام + دليل + عبارة فريدة)؛ **ووُصلت بمبدّل اللغة ٢٠٢٦-٠٨-٠٩ — «لا /en» يحكم الـURLs لا لغة الواجهة**؛ **ومرحلة ٥ (٠٨-١٥): جملة مؤرَّخة مطلقة لكل موسم بدل العدّاد النسبي + الأسئلة ١٠←١٥ · ومرحلة ٦: نفس الحركة على `/national-day` والأسئلة ٤←٩**
- [Occasion Page Relevance Filter](occasion_page_relevance_filter.md) — store_tags تصنيف لا موسم؛ + master.occasions (migration_067)
- [💳 التقسيط: هَب /installments](web_installments_bnpl.md) — تابي/تمارا/مدفوع مزحوفة لا مُدخلة؛ **الرئيسية وحدها كذبت** (المنيع صفر بها و٣٢ بصفحة قسم)؛ والغياب ليس نفياً
- [🔐 جلسة الويب في كوكي HttpOnly](web_session_httponly_cookie.md) — انتقلت ٢٠٢٦-٠٨-٢٧؛ **الميني-آب بأصل `null` فالترويسة تبقى للأبد**؛ الكوكي يسبقها؛ والباك-إند يُنشر أولاً وإلا جلسات ميتة
- [🎯 صفّ «صفقات تهمّك»](web_home_interests_rail.md) — أول قارئ لإشارات `action_logs`؛ التسجيل في `trackAction` لا المكوّنات؛ **hook في `lib/` يصله `api.ts` يكسر البناء كلّه**
- [Web Login Gate Model](web_login_gate_model.md) — الموقع مفتوح؛ الستوري/المفضلة للمسجّلين؛ حركات المجهول بـvisitor_id
- [Store Page Evergreen (404 Root Cause)](store_page_evergreen.md) — `last_time>=CURRENT_DATE` أخفى المتجر → 404؛ المتجر دائم والكوبون يُفرَّغ

## ٥) التحليلات والسيو (٣٣)

- [🎯 منظومة إدارة الحملات](campaign_system.md) — ٧ فحوص تمنع إطلاق حملة لا تُقاس · قراءة لا تُغلق بلا فعل · **صفوف `seo_perf_snapshots` نوافذ ٢٨ يوماً لا أياماً (لا تُجمع)** · والكتابة على عمود جديد تُبنى متكيّفة لأن الكود يسبق المايجريشن
- [📈 GA4 رُكِّب — ومربوط بمفاتيح اللوحة](web_ga4_install.md) — `G-VRBHD0VK66` حيّ على ٦ مسارات؛ **لا `page_view` يدويّ فالقياس المحسّن هو من يرصد تنقّل Next**؛ وCSP كانت ستحجبه بصمت؛ و**قلب مفتاح «إشارات Google» يُلزِم تعديل نصّ الخصوصية في نفس الجلسة**؛ ومرجع الحملات `seo/ads_measurement_doctrine.md` (**١٩ درساً مقروءاً؛ نموذجنا اسمه OCI**) والدورة `seo/ga4_curriculum.md` (مبتدئ مكتمل؛ **الاحتفاظ رجعيّ وغير طارئ، والطارئ BigQuery**) والدليل التنفيذي `seo/ga4_playbook.md` (١١ مهمة مصنَّفة + BigQuery تأميناً + GA4 أعمى عن قناة الـAI)
- [🧪 فلتر النصائح الخارجية](seo_external_advice_filter.md) — كل سلسلة SEO تُصنَّف قبل التنفيذ؛ ٧ من ١٠٠ ضارّة عندنا؛ **+ كتاب حسوب ٠٨-١٨: اقرأ تاريخ المادة — ٣ فصول توصي بأدوات سحبتها جوجل**؛ الوجهة skill `dealpulse-seo`
- [📚 مصادر تعلّم السيو](seo_learning_sources.md) — `seo/learning_sources.md`: ١٤ مصدراً مفحوصاً بأربع طبقات + محرّك سحب مُختبَر؛ **الأوّلية وحدها مصدر حقيقة** و`incidents.json` يؤرّخ كل تحديث

- تحليل المتاجر: [الجناح](store_analytics_bi.md) (٤ تبويبات + AI عبر Groq) · [استراتيجية إعادة البناء](analysis_rebuild_strategy.md) (٦ صفحات، ٣ مسارات دخل، zero-fakery) · [البنية النهائية](analytics_store_structure.md) (٦ أقسام؛ «أبرز» = top favorites)
- الكلمات المفتاحية: [⛔ Keyword Planner](google_ads_keyword_planner.md) (**رفضته Google نهائياً — التكامل مُتراجَع عنه بـ5ad4f7b، لا كود حيّ**) · [طلب السوق السعودي](keyword_demand_ksa.md) (البراندات 10K-100K؛ متاجرك ~10-100) · [⚠️ Windsor GSC](windsor_gsc_connector.md) (المجاني يرجع أصفاراً وهمية بلا خطأ)
- [SEO Indexation Status](seo_indexation_status.md) — الفهرسة 4→150؛ انفجار ظهور يوليو؛ العنق = المركز+CTR
- [SEO Deep Audit Fixes](seo_deep_audit_fixes.md) — بق light-AR 500 (is_trending BOOLEAN) أفرغ الخريطة صامتاً؛ اسحب الباك-إند أولاً
- [SEO Authority Building](seo_authority_building.md) — crawled-not-indexed سقف سلطة؛ باكلينكس White-Hat؛ **+ ٠٨-١٨: صفر رابط خارج لأي تاجر ⇒ مسار الشركاء ليس تبادلاً (٥ أهداف بدليل مالي)**
- [SEO High-Demand Front](seo_high_demand_front_opened.md) — فخّ AR=draft+EN=noindex؛ نُشرت 23 صفحة؛ نون/نمشي محجوبان بالسلطة
- [🤖 AI Citation Channel](ai_citation_channel.md) — **٤١٣ استشهاد Copilot/٣٠ يوماً مقابل ١٣٢ نقرة جوجل**؛ يقاس بـBing AI Performance؛ **يسقط حكم «صفر نقرة = ميت»**؛ قاعدتان لا واحدة
- [SEO Page Portfolio Verdict](seo_page_portfolio_verdict.md) — ٧١٠/٧٦٤ صفحة صفر نقرة؛ المتاجر نيّة ميتة؛ التجميع وحده يكسب — ⚠️ **عُدِّل بـ[[ai_citation_channel]]: صفر نقرة ≠ صفر قيمة**
- [SEO Category Query Alignment](seo_category_query_alignment.md) — وزن المفردات: «كوبون» م49 و«متاجر» م19؛ ٨٧٪ من الظهور غارق؛ CTR المتاجر منخفض **بقرار الإسناد** لا بعطل
- [🔁 تكاذُب /c/ ↔ /store](seo_c_store_cannibalization.md) — صفحتان بعنوان واحد تُسقطان الترتيب؛ canonical مشتقّ لـ١٩ + اسم المتجر العربي مضمون بكل عنوان
- [🔴 SEO Meta Code — التفريع نُسِخ](seo_meta_code_leak.md) — الكود يُكشف لكل الكتالوج في سنِبت المتجر **و llms.txt**؛ isCodeAttributed لشارات المدوّنة فقط
- [⚖️ ثقة أدوات الفحص](seo_audit_tools_trust.md) — **آخر يومين في GSC ناقصان (سقوط كل الخطوط معاً = تأخّر لا هبوط)**؛ «هبوط الترافيك» في Ahrefs تقدير لا قياس؛ سيمرش مجمّد + عيّنة ٦٪ — **+ ٠٨-١٩: بندٌ رقمه = عدد صفحات الموقع ⇒ المصدر قالبيّ (الفوتر)، وصفوف «changed» تُعزى لالتزاماتك أنت**
- الفهرسة: [Google Indexing حيّ](seo_google_indexing_live.md) (٢٠٠/يوم) · [الدفع بالجملة](seo_bulk_reindex_ops.md) (دفعات ٦؛ IndexNow بلا حصة؛ Yandex 202 = نجاح) · [الظهور لمحرّكات AI](seo_ai_visibility_optin.md) (١٥ كراولر + llms.txt)
- الترويج: [محور القنوات المملوكة](seo_owned_channels_pivot.md) (رفض Reddit/Quora؛ X+Telegram+IG) · [PR Blitz Kit](seo_pr_blitz_kit.md) (لترويج /calendar)
- [🔗 SaaSHub Directory Listing](saashub_directory_listing.md) — رابط الدليل nofollow حتى تُوثَّق الملكية (٢٢ صفحة مقيسة)؛ التوثيق مجاني بلا رابط متبادل
- الدومين: [خطة السلطة](domain_authority_plan.md) (**الهَب السِتوايد أُعيد توجيهه للمناسبات ٢٠٢٦-٠٨-٠٨**؛ المتبقّي باكلينك) · [⚠️ فخّ الـcanonical](domain_canonical_trap.md) (الصح dealpulseksa.com؛ dealpulesksa ميّت)
- [Content/Programmatic Strategy](content_programmatic_strategy.md) — «عربي فقط لا /en»؛ category-content + هَب أقسام؛ لا صفحات رقيقة
- [Seasonal School Traffic Bridge](seasonal_school_traffic_bridge.md) — عنقود المدرسة يجرّ سعوديين موسمياً؛ الجسر ١٣ رابط
- [Competitor Landscape](competitor_landscape.md) — الموفّر القائد؛ الفجوات: تحقّق/تيليجرام/نيش محلي/AEO — **+ فحص ٠٨-١٥: لا كارتل يملك هَب تقويم مؤرَّخاً (فجوة بنيوية) وتواريخهم بائتة**
- [🔌 Claude SEO Plugin](claude_seo_plugin.md) — ١٨ agent+٢٥ skill مثبَّتة بمستوى الريبو عبر `.claude/settings.json` (لا الجهاز)؛ خريطة أولوية للعناقيد الحالية؛ **السحابة محجوبة عن dealpulseksa.com — تدقيق فعلي شغل ترمنال فقط**
- [🏺 قصر الاواني — مصدر الحقيقة](qasr_alawani_source_of_truth.md) — GraphQL مفتوحة تعطي شجرة الأقسام بأعدادها؛ **robots يسمح لـGooglebot وحده وخرائطهم 404**؛ والاسم بلا همزة؛ ومدفوع داخل صورة فالزاحف أعماه
- [🚕 مصادر لائحة نقل الركاب](ride_hailing_regulation_sources.md) — نصّ اللائحة على أم القرى + endpoint قائمة المرخّصين + أرقام متجر التطبيقات؛ الأمان يُبنى على النصّ لا على الصفة

## ٦) المحتوى والمدوّنة (٢٠)

- [Voice Bible](voice_bible.md) — نموذج الصوت التحريري (عيّنة فيتامين د مشرَّحة)؛ قلّد العيّنة
- [Blog Total = Count It Live](blog_massive_content_session.md) — **١٥٦٤ (عُدَّ ٢٠٢٦-٠٨-٠٨؛ كان ١٤٨١ قبل ٣ أيام)**؛ عُدّ بـ`grep -cE "^\s*slug:" lib/blog.ts` لا تجمع تقديرياً
- الصحّة: [عنقود المكمّلات](health_content_cluster.md) (١٠ مقالات iHerb؛ كود QQC1568) · [مصادر الاستشهاد](health_citation_sourcing.md) (Mayo/NIH يحجبان الـcrawlers = 403 كاذب؛ استخدم Harvard)
- [Blog Internal-Link De-orphan](blog_internal_link_deorphan.md) — 65 مقال يتيم صُفِّرت؛ top-6 getRelatedPosts يجوّع الذيل
- [Blog Inline Code Chips](blog_inline_code_chips.md) — شارة كود/CTA بجانب كل ذكر متجر في ١٣٦٥ مقال؛ العلاج بالعارض
- [Jolina Pre-Purchase Angle](jolina_prepurchase_angle.md) — الزاوية «الاسترجاع/الرسوم» لا الكود؛ مواقع JS لا تُقرأ بـcurl
- عناقيد كبرى: [١٤ متجر/٢٨٠ مقال](blog_14clusters_july11.md) · [٧ عناقيد/١٠٥](blog_7clusters_july11.md) · [AliExpress ١٥٠ — نقّها+noindex](blog_aliexpress_cluster.md) · [ألعاب ١٠/٧٢](blog_toys_cluster_progress.md)
- [💇 عنقود نزيه — ست ممرّات فارغة](blog_nazih_cluster.md) — ١٤ مقالاً على أقسام بلا متجر ولا مقال؛ لا تغزُ عنقود شريك؛ وعُدَّ الروابط الداخلة **لكل مقال** لا للعنقود
- عناقيد متاجر (١٢–١٩ مقالاً لكلٍّ، ربط متبادل): [ذا ديل](blog_thedeal_cluster.md) · [فوغا كلوسيت](blog_vogacloset_cluster.md) · [ماماز](blog_mamaspapas_cluster.md) · [H&M](blog_hm_cluster.md) · [بيد إن روم](blog_bedinroom_cluster.md) · [لحظات القهوة](blog_lahazat_cluster.md) · [جنى العسل](blog_jana_honey_cluster.md) · [عبدالصمد القرشي](blog_asq_cluster.md) · [أثاث المنزل](blog_home_furniture_cluster.md)

## ٧) قنوات الأفلييت والشراكات (١٢)

- سلة: [القناة](salla_affiliate_channel.md) (خصم+عمولة بلا بوّابة ✅) · [الإسناد بالكود لا النقرة](salla_orders_attribution_reality.md) · [٦ متاجر محوِّلة · ٨٠٧٫٥٤ ر.س](salla_proven_converters.md) (لقطة ٠٨-٢٤؛ نِسب تحويل >١٠٠٪ = إسناد بالكود)
- Admitad: [الإعداد](admitad_affiliate_setup.md) (مساحتان + بوّابتان) · [حجب ISP للنطاق](admitad_dns_block.md) (NXDOMAIN مزوّر → DNS مشفّر)
- [CodeMap Affiliate Channel](codemap_affiliate_channel.md) — كوبونات فقط بلا تتبّع؛ براندات كبيرة؛ تكمّل سلة
- [Boostiny Publisher Channel](boostiny_publisher_channel.md) — قُبل ٢٠٢٦-٠٨-٠٦ (#52131)؛ الملف قُدِّم ومقفول → مراجعة ثانية ثم اتفاقية
- [DCM Network Channel](dcm_network_channel.md) — ٣ منصّات؛ ندرة أكواد أقفلت الحساب؛ ليس رافعة نمو
- [Zid Affiliate Channel](zid_affiliate_channel.md) — سفير زد: عمولة 30%/خصم 20%، إسناد بالرابط فقط
- [Jahez Direct BD](jahez_direct_bd.md) — تواصل مباشر بلا شبكة؛ البريد من زيارة المقر؛ مسوّدة في outreach/
- [📄 الملف التعريفي بنسختين](company_profile_bilingual.md) — AR+EN ٨ صفحات؛ **قرارات المالك: وثيقة عمل حر فقط، لا حالات بأرقام/أسماء، لا صفحة مؤسس**؛ وفخّ القصّ الصامت (`overflow:hidden`) وفاحصه
- [Affiliate PPC Brand Restrictions](affiliate_ppc_brand_restrictions.md) — منع المزايدة المدفوعة على البراند؛ SEO عضوي مسموح
- [Contact Emails](contact_emails.md) — الصح `dealpulseksa@gmail.com`؛ `dealpules` خطأ مثبّت بالكود؛ + إيميل DCM

## ٨) التسويق والسوشيال (٧)

- [Marketing Baseline & Strategy](marketing_baseline_and_strategy.md) — ~121 سعودي/شهر (89% بوتات)؛ العنق الترافيك لا التحويل
- انستقرام: [محرّك المحتوى](instagram_content_engine.md) (ريلز Dark Luxe؛ «الحساب ميت» = الصيغة غلط لا shadow-ban) · [محرّك النمو](ig_growth_engine.md) (caption SEO + auto-publish + /ig) · [سياسة النشر](ig_publish_policy.md) (لا ستوري تلقائية؛ ريل كل ٦ بثّات)
- [Brand Face for Flow Reels](brand_face_reels.md) — بنت خضراء سعودية (brand_face_crop.png)؛ نطق «نبض الصفقات»
- [Social Listening Deferred](social_listening_deferred.md) — الرصد الاجتماعي/رادار الصفقات مؤجَّلان (مصادر ميتة)
- [Local TTS — XTTS v2 (REMOVED)](tts_engine_xtts_v2.md) — بُني وحُذف؛ عربي محلي ضعيف؛ الطريق API عصبي مدفوع

### صيانة الفهرس — **كل ملف على القرص يجب أن يظهر هنا** (حدث: ٤ ملفات مخفيّة أسابيع)

```powershell
$idx=(Get-Content Claude_Memory\MEMORY.md -Encoding UTF8|%{[regex]::Matches($_,'\(([^)]+\.md)\)')|%{$_.Groups[1].Value}})
(Get-ChildItem Claude_Memory -Filter *.md|?{$_.Name -ne 'MEMORY.md'}).Name|?{$idx -notcontains $_}
```
