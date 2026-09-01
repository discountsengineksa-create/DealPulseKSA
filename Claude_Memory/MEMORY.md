# Project Memory Index

> ١٥٤ ملفاً (عُدّت ٢٠٢٦-٠٨-٣٠ بعد ملف تعريب اسم البراند — `ls *.md | grep -v MEMORY.md | wc -l` = ١٥٤). **العدّ للمتون، بلا `MEMORY.md` نفسه**. **الفهرس وحده يُحمَّل — المتون لا.** السطر هنا **عنوان لا حقيقة**؛ الحقيقة في المتن.
> **الطبقة ٠ تُقرأ متونها قبل أي مهمة.** من الباقي: افتح ما يخصّ مهمتك وأعلن ما فتحته.
> الحوائط الصلبة منسوخة نصّاً في `CLAUDE.md`. سطرٌ بعدّة روابط = ملفات مستقلة جُمعت للاختصار.

## 🔴 الطبقة ٠ — اقرأ متونها قبل أي مهمة (١٣)

- [🧱 تحقّق من كتالوج المتجر الحيّ قبل أي ادّعاء](feedback_verify_catalog_before_claim.md) — لا تشتقّ منتجاً من التاق؛ درس سيدار: ٨٩ ادّعاءً مفبركاً عبر ٥٥ مقالاً
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

- [🔥 ضبط حرق التوكنز](feedback_token_burn_control.md) — تكلفة الدور = المحادثة كلها؛ الصور تسكن السياق للأبد؛ العدّاد في statusline
- [User Preferences](user_preferences.md) — how the user likes to work
- [Analysis Style](feedback_analysis_style.md) — جداول مقارِنة تقود قراراً؛ أفعال وأكواد لا كلام ملمّع؛ أقفل الصفحة قبل التالية
- [Judge by Output](feedback_output_over_engineering.md) — يقيّم بالمخرَج لا صعوبة السباكة؛ اكشف سقف الأداة بصراحة
- [Regression Audit First](feedback_regression_audit.md) — «كان يشتغل قبل تغييرك» → افحص diffs الأخيرة أولاً
- [Check .env First](feedback_check_env_first.md) — مشاكل config: اقرأ .env + endpoints أولاً ثم Railway
- [No Dead Code / No Premature Opt](feedback_no_dead_code.md) — كل سطر حقيقي موصول مبرّر ببوتلنك فعلي
- [Zero Friction Onboarding](feedback_zero_friction.md) — اجمع البيانات عند نقطة القيمة (action-gated) لا الدخول
- [Store Selection Criterion](feedback_store_selection.md) — معرفة السعودي+السياق تغلب العمولة؛ أبقِ المعروف احذف الغريب
- [Prefer Codes over Tracking Links](feedback_prefer_codes_over_tracking_links.md) — الأكواد لا روابط التتبّع
- [Never Publish Competing Codes](feedback_never_publish_competing_codes.md) — لا تذكر كود المتجر الترحيبي ولو كان أعلى
- [Always Publish When Done](feedback_always_publish.md) — auto commit+push عند الإنجاز؛ main=prod؛ لا تسأل
- [No Backticks in blog.ts Literals](feedback_no_backticks_in_template_literals.md) — ``` داخل body يكسر SWC
- [AI Mastery Goal](user_ai_mastery_goal.md) — يريد برومبت عالمي معاد الاستخدام؛ رأي خبير صريح
- العقل المدبر: [البروتوكول](protocol_mastermind.md) · [البرومبت](mastermind_prompt.md)
- [Memory Sync via Junction](memory_sync_junction.md) — ذاكرة واحدة بالريبو + junction؛ تتزامن مع git؛ لا تفرّع
- [☁️ Claude Code Cloud Sessions](claude_code_cloud_sessions.md) — claude.ai/code + الجوال مربوطان بالريبو؛ يرثان الذاكرة لكن بلا `.env`
- المهارات: [المثبَّتة](skills_install_manifest.md) (٢٩٦ skill + ٢٥ أمراً؛ لا مهارة RTL/عربية) · [عدّة التسويق](marketing_skills_toolkit.md) (١٧ skill؛ عربي سعودي)
- [Reconcile Web Repo Separately](reconcile_web_repo_separately.md) — dealpulseksa-web ريبو مستقل؛ افحصه أولاً

## ٢) البنية والتشغيل والنشر والموقع (١٩)

- أساسيات: [نظرة عامة](project_overview.md) · [الإعداد المحلي](setup_guide.md) · [سجلّ الإصلاحات](bug_fixes.md)
- Railway: [النشر](railway_deployment.md) (الخدمة الموحّدة، tag الرجوع) · [عامل الجدولة](railway_scheduler_worker.md) (config منفصل، cron ≥5د)
- [Single Source of Truth](single_source_of_truth.md) — DB واحد + داشبورد واحد؛ .env على Railway فقط
- [Platform Monitoring](platform_monitoring.md) — «متابعة المنصة»: صفحة + ضوابط + تقرير صحة + أداء API
- [🔒 Security Hardening](security_hardening.md) — فحص أمني (صفر ثغرة حرجة)؛ CSP بـnext.config؛ /docs مقفول بالإنتاج
- متفرقات تشغيلية: [سعة البوت](bot_capacity_scaling.md) (سقف ~30/ث) · [ميزات مُنجَزة](project_completed_features.md) · [البريد](project_email_infrastructure.md) (Resend) · [خطة الأسابيع](weeks_roadmap.md) · [معسكر ريادة](entrepreneur_bootcamp.md)
- الموقع: [المشروع](website_project.md) (Next.js+Firebase) · [التصميم](website_design_preferences.md) · [محرّك السيو](website_seo_engine.md)
- [Web Repo Verification Recipes](web_repo_verification_recipes.md) + [Blog OOM/Client-Prop](web_blog_monolith_oom_and_client_prop_serialization.md) — tsconfig ضيّق يتجاوز OOM؛ قصّ related لصفحة >2MB
- [🎟️ Coupon Visual Identity](web_coupon_visual_identity.md) — نُشرت ٢٠٢٦-٠٨-١١؛ **`view=light` يرجّع الكود/الرابط `null`**؛ الترند وُصل بالكتالوج
- [🎫 Logo: Ticket + DP](brand_logo_ticket_2026_08.md) — اعتُمد ٢٠٢٦-٠٨-١٢؛ **الفافيكون الحالي ١٦×٨ بكسل**
- [🎨 الهوية طُبِّقت على الأسطح الأربعة](brand_identity_applied.md) — `brand.py`+`style.css` مصدر الحقيقة؛ **ملفّات الخط `-ar` مجزّأة فطبعت مربّعات**

## ٣) قاعدة البيانات وموثوقية الأرقام (٩)

- [DB Foundation Audit](db_foundation_audit.md) — **حيّ ٢٠٢٦-٠٨-٠٥: ٧١ جدول / ٣٨ فارغ (٥٤٪) / master ٥٢**؛ دَيْن النوع بلا contract
- [master.store_id غير فريد](db_master_duplicate_store_id.md) · [المحلي منفصل عن الإنتاج](db_local_vs_railway.md)
- تتبّع/جغرافيا: [ثقة البيانات](data_trust_geo_device.md) (city/device مفبركة) · [قواعد تحليل المستخدمين](users_analytics_rules.md) · [Web Visits](web_visits_tracking.md) (Migration 060)
- [Unified Favorites](unified_favorites.md) — user_favorites SSOT + كتابة مزدوجة **حيّة**؛ **الإزالة لا تُسجَّل**
- [Bot-vs-Promo 3-Signal Check](bot_vs_promo_heuristic.md) — قبل اتّهام قفزة بالبوت: visitor_id + timing + ASN
- [Owned Audience Reality](owned_audience_reality.md) — ٥ مستخدمي بوت + ١٠ حسابات ويب + صفر بثّ؛ **لا تقرير أداء لشريك أبداً**

## ٤) ميزات المنتج (١١)

- [🔎 طبقة البحث الذكي](search_intelligence_layer.md) — تطبيع عربي + `search_concepts` (مرادف→قسم) + `blog_bridge` (كلمة→مقال→متاجره)؛ **حيّ ٢٠٢٦-٠٨-٣٠**؛ أعِد `build_blog_bridge --write` بعد أي تعديل مدوّنة
- ترند: [البنية النهائية](trend_architecture_final.md) (١٤ قرار) · [source='all'](trend_source_all.md) (DB واحد، البوت بلا ستوري)
- [Story System Design](story_system_design.md) — story_slides؛ نموذج متداخل؛ فيديو+صوت؛ Cloudinary
- [Support System](support_system.md) · [Publish Channels](publish_channels_feature.md) · [Season Reminders](season_reminders_feature.md)
- [Calendar Conversion Hub](calendar_conversion_hub.md) — كل موسم بوابة؛ **«لا /en» يحكم الـURLs لا لغة الواجهة**؛ مرحلة ٥/٦: جملة مؤرَّخة مطلقة بدل العدّاد النسبي
- [Occasion Page Relevance Filter](occasion_page_relevance_filter.md) — store_tags تصنيف لا موسم؛ + master.occasions
- [💳 التقسيط: هَب /installments](web_installments_bnpl.md) — تابي/تمارا/مدفوع مزحوفة لا مُدخلة؛ **الرئيسية وحدها كذبت**
- [🔐 جلسة الويب في كوكي HttpOnly](web_session_httponly_cookie.md) — انتقلت ٢٠٢٦-٠٨-٢٧؛ **الميني-آب بأصل `null` فالترويسة تبقى للأبد**
- [🎯 صفّ «صفقات تهمّك»](web_home_interests_rail.md) — `?interest=`/`?cat=` + `IntentPicker`؛ **hook في `lib/` يصله `api.ts` يكسر البناء**
- [Web Login Gate Model](web_login_gate_model.md) — الموقع مفتوح؛ الستوري/المفضلة للمسجّلين
- [Store Page Evergreen (404 Root Cause)](store_page_evergreen.md) — `last_time>=CURRENT_DATE` أخفى المتجر → 404

## ٥) التحليلات والسيو (٣٣)

- [🎯 منظومة إدارة الحملات](campaign_system.md) — ٧ فحوص تمنع إطلاق حملة لا تُقاس؛ **صفوف `seo_perf_snapshots` نوافذ ٢٨ يوماً لا أياماً**
- [📈 GA4 رُكِّب — ومربوط بمفاتيح اللوحة](web_ga4_install.md) — `G-VRBHD0VK66`؛ **لا `page_view` يدويّ**؛ مرجع الحملات/الدورة/الدليل داخل الملف
- سيو خارجي: [فلتر النصائح](seo_external_advice_filter.md) (٧ من ١٠٠ ضارّة) · [مصادر التعلّم](seo_learning_sources.md) (١٤ مصدراً مفحوصاً)
- [🔤 تحقّق من تعريب اسم البراند قبل SEO](seo_verify_brand_transliteration.md) — Autocomplete السعودي يحكم؛ درس ناتشورال تاتش (أُدخل «ناشيونال تاتش» خطأً) + بيانات قناته
- تحليل المتاجر: [الجناح](store_analytics_bi.md) · [استراتيجية إعادة البناء](analysis_rebuild_strategy.md) · [البنية النهائية](analytics_store_structure.md)
- الكلمات المفتاحية: [⛔ Keyword Planner](google_ads_keyword_planner.md) (مرفوض نهائياً) · [طلب السوق](keyword_demand_ksa.md) · [⚠️ Windsor GSC](windsor_gsc_connector.md) (يرجع أصفاراً وهمية)
- [SEO Indexation Status](seo_indexation_status.md) + [Deep Audit Fixes](seo_deep_audit_fixes.md) — فهرسة 4→150؛ بق light-AR 500 أفرغ الخريطة صامتاً
- [SEO Authority Building](seo_authority_building.md) — crawled-not-indexed سقف سلطة؛ **صفر رابط خارج لأي تاجر ⇒ مسار الشركاء ليس تبادلاً**
- [SEO High-Demand Front](seo_high_demand_front_opened.md) — فخّ AR=draft+EN=noindex؛ نون/نمشي محجوبان بالسلطة
- [🤖 AI Citation Channel](ai_citation_channel.md) — **٤١٣ استشهاد Copilot/٣٠يوم مقابل ١٣٢ نقرة جوجل**؛ **+ ٠٨-٢٧: GA4 أكّدها بنقرة حقيقية — قناة AI Assistant ٤٥ جلسة/٧أيام**
- [SEO Page Portfolio Verdict](seo_page_portfolio_verdict.md) — ٧١٠/٧٦٤ صفحة صفر نقرة — ⚠️ **عُدِّل بـ[[ai_citation_channel]]: صفر نقرة ≠ صفر قيمة**
- [SEO Category Query Alignment](seo_category_query_alignment.md) — وزن المفردات: «كوبون» م49 و«متاجر» م19؛ ٨٧٪ من الظهور غارق
- تكاذُب/تسريب: [/c/ ↔ /store](seo_c_store_cannibalization.md) (canonical مشتقّ لـ١٩) · [Meta Code Leak](seo_meta_code_leak.md) (الكود يُكشف بـllms.txt أيضاً)
- [⚖️ ثقة أدوات الفحص](seo_audit_tools_trust.md) — آخر يومين GSC ناقصان (تأخّر لا هبوط)؛ «هبوط الترافيك» في Ahrefs تقدير لا قياس
- الفهرسة: [حيّ](seo_google_indexing_live.md) (٢٠٠/يوم) · [الدفع بالجملة](seo_bulk_reindex_ops.md) · [الظهور لمحرّكات AI](seo_ai_visibility_optin.md) (١٥ كراولر)
- الترويج: [القنوات المملوكة](seo_owned_channels_pivot.md) (رفض Reddit/Quora) · [PR Blitz Kit](seo_pr_blitz_kit.md)
- [🔗 SaaSHub Directory Listing](saashub_directory_listing.md) — رابط nofollow حتى تُوثَّق الملكية
- الدومين: [خطة السلطة](domain_authority_plan.md) (الهَب السِتوايد أُعيد توجيهه للمناسبات) · [⚠️ فخّ الـcanonical](domain_canonical_trap.md) (dealpulesksa ميّت)
- [Content/Programmatic Strategy](content_programmatic_strategy.md) — «عربي فقط لا /en»؛ لا صفحات رقيقة
- [Seasonal School Traffic Bridge](seasonal_school_traffic_bridge.md) + [Competitor Landscape](competitor_landscape.md) — لا كارتل يملك هَب تقويم مؤرَّخاً
- [🔌 Claude SEO Plugin](claude_seo_plugin.md) — ١٨ agent+٢٥ skill بمستوى الريبو؛ **السحابة محجوبة عن dealpulseksa.com**
- [🏺 قصر الاواني](qasr_alawani_source_of_truth.md) + [🚕 لائحة نقل الركاب](ride_hailing_regulation_sources.md) — مصادر أوّلية مفحوصة للاستشهاد

## ٦) المحتوى والمدوّنة (٢٠)

- [Voice Bible](voice_bible.md) — نموذج الصوت التحريري؛ قلّد العيّنة
- [Blog Total = Count It Live](blog_massive_content_session.md) — **١٥٦٤ (عُدَّ ٢٠٢٦-٠٨-٠٨)**؛ عُدّ بـ`grep -cE "^\s*slug:" lib/blog.ts` لا تجمع تقديرياً
- الصحّة: [عنقود المكمّلات](health_content_cluster.md) · [مصادر الاستشهاد](health_citation_sourcing.md) (Mayo/NIH يحجبان الـcrawlers)
- [Blog Internal-Link De-orphan](blog_internal_link_deorphan.md) — 65 مقال يتيم صُفِّرت؛ top-6 getRelatedPosts يجوّع الذيل
- [Blog Inline Code Chips](blog_inline_code_chips.md) + [Jolina Pre-Purchase Angle](jolina_prepurchase_angle.md) — الزاوية «الاسترجاع» لا الكود
- عناقيد كبرى: [١٤ متجر/٢٨٠ مقال](blog_14clusters_july11.md) · [٧ عناقيد/١٠٥](blog_7clusters_july11.md) · [AliExpress ١٥٠](blog_aliexpress_cluster.md) · [ألعاب ١٠/٧٢](blog_toys_cluster_progress.md)
- [💇 عنقود نزيه — ست ممرّات فارغة](blog_nazih_cluster.md) — لا تغزُ عنقود شريك؛ عُدَّ الروابط **لكل مقال** لا للعنقود
- عناقيد متاجر (١٢–١٩ مقالاً لكلٍّ): [ذا ديل](blog_thedeal_cluster.md) · [فوغا كلوسيت](blog_vogacloset_cluster.md) · [ماماز](blog_mamaspapas_cluster.md) · [H&M](blog_hm_cluster.md) · [بيد إن روم](blog_bedinroom_cluster.md) · [لحظات القهوة](blog_lahazat_cluster.md) · [جنى العسل](blog_jana_honey_cluster.md) · [عبدالصمد القرشي](blog_asq_cluster.md) · [⚠️ أثاث المنزل — سيدار لا يبيع أثاثاً](blog_home_furniture_cluster.md)

## ٧) قنوات الأفلييت والشراكات (١٢)

- سلة: [القناة](salla_affiliate_channel.md) · [الإسناد بالكود](salla_orders_attribution_reality.md) · [٦ متاجر محوِّلة · ٨٠٧٫٥٤ ر.س](salla_proven_converters.md)
- Admitad: [الإعداد](admitad_affiliate_setup.md) · [حجب ISP للنطاق](admitad_dns_block.md)
- شبكات أخرى: [CodeMap](codemap_affiliate_channel.md) (كوبونات بلا تتبّع) · [Boostiny](boostiny_publisher_channel.md) (قُبل ٠٨-٠٦) · [DCM](dcm_network_channel.md) (ليس رافعة نمو) · [Zid](zid_affiliate_channel.md) (سفير زد)
- [Jahez Direct BD](jahez_direct_bd.md) — تواصل مباشر بلا شبكة؛ مسوّدة في outreach/
- [📄 الملف التعريفي بنسختين](company_profile_bilingual.md) — AR+EN؛ **لا حالات بأرقام/أسماء، لا صفحة مؤسس**
- [Affiliate PPC Brand Restrictions](affiliate_ppc_brand_restrictions.md) · [Contact Emails](contact_emails.md) (`dealpulseksa@gmail.com`)

## ٨) التسويق والسوشيال (٧)

- [Marketing Baseline & Strategy](marketing_baseline_and_strategy.md) — **حُدّث 2026-09-01: 546 سعودي بشري/30ي (×4.5)، GSC 336 نقرة/28ي، محرّك واحد كاسب = المواسم**؛ ثغرات: opportunity_keywords فارغ، landing_pages perf NULL، GA4 غير موصول بـWindsor
- انستقرام: [محرّك المحتوى](instagram_content_engine.md) (ريلز Dark Luxe) · [محرّك النمو](ig_growth_engine.md) (caption SEO) · [سياسة النشر](ig_publish_policy.md) (لا ستوري تلقائية)
- [Brand Face for Flow Reels](brand_face_reels.md) — بنت خضراء سعودية؛ نطق «نبض الصفقات»
- [Social Listening Deferred](social_listening_deferred.md) — الرصد الاجتماعي مؤجَّل (مصادر ميتة)
- [Local TTS — XTTS v2 (REMOVED)](tts_engine_xtts_v2.md) — بُني وحُذف؛ عربي محلي ضعيف

### صيانة الفهرس — **كل ملف على القرص يجب أن يظهر هنا**

```powershell
$idx=(Get-Content Claude_Memory\MEMORY.md -Encoding UTF8|%{[regex]::Matches($_,'\(([^)]+\.md)\)')|%{$_.Groups[1].Value}})
(Get-ChildItem Claude_Memory -Filter *.md|?{$_.Name -ne 'MEMORY.md'}).Name|?{$idx -notcontains $_}
```
