# Project Memory Index

> ٢٠٠ ملفاً (عُدّت ٢٠٢٦-٠٩-١٤). الفهرس وحده يُحمَّل — المتون لا. السطر هنا عنوان لا حقيقة؛ الحقيقة في المتن.
> الطبقة ٠ تُقرأ متونها قبل أي مهمة. من الباقي: افتح ما يخصّ مهمتك وأعلن ما فتحته.
> الحوائط الصلبة منسوخة نصّاً في `CLAUDE.md`. سطرٌ بعدّة روابط = ملفات مستقلة جُمعت للاختصار.

## 🔴 الطبقة ٠ — اقرأ متونها قبل أي مهمة (١٥)

- [🧱 تحقّق من كتالوج المتجر الحيّ قبل أي ادّعاء](feedback_verify_catalog_before_claim.md) — لا تشتقّ منتجاً من التاق؛ درس سيدار: ٨٩ ادّعاءً مفبركاً عبر ٥٥ مقالاً
- [🤝 Partnership Protocol](protocol_partnership.md) — ٨ أنماط بالاسم + دورة انضباط + طقوس جلسة + سياسة المصادر
- [No Philosophy — Just Execute](feedback_no_philosophy.md) — لا خيارات/تمهيد؛ ابدأ بالأوضح؛ سؤال نصّي واحد عند العجز
- [Treat User as Senior Engineer](feedback_senior_engineer.md) — خبير ٢٠+؛ لا فلسفة/خيارات/أساسيات؛ اقرأ حدّد نفّذ
- [🧱 No DB Writes Without Permission](feedback_no_db_writes_without_permission.md) — INSERT/UPDATE/DELETE يحتاج إذناً صريحاً؛ «يلا نبدا» ليس إذناً
- [🚧 الهارنس يحجب الوكيل عن كتابة DB وتعديل صلاحياته بنفسه](feedback_harness_blocks_self_permission.md) — حتى بإذن المالك؛ الحلّ: المالك يلصق قاعدة الصلاحية بنفسه
- [🧱 لا حذف من الكتالوج ولا من المدوّنة](feedback_never_delete_catalog_or_content.md) — متجر/مقال لا يُحذف إلا بطلب شخصي؛ التوصية مسموحة والتنفيذ ممنوع
- [🧱 Always Push, Never Leave Work Local](feedback_always_push.md) — أجهزة متعددة؛ push كل شيء، لا stash، pull بالبداية
- [🧱 SEO White-Hat Only](seo_white_hat_only.md) — White-Hat فقط؛ محرّك ببوابات؛ SEO_AUTO_PUBLISH على DEALPULSEKSA
- [🛡️ Content Guardrails Playbook](content_guardrails_playbook.md) — سلامة/YMYL + صفر فبركة + تنسيق + ربط داخلي + صراحة استراتيجية
- [🔓 Full Authority Granted](feedback_full_authority.md) — تفويض ذاتي على الأفعال المحلية القابلة للعكس (لا يبطل حوائط DB/الحذف)
- [🔓 Bot Freeze LIFTED](bot_frozen_lock.md) — البوت مفكوك ٢٠٢٦-٠٧-٠٧ ضمن البروتوكول؛ حوائط DB/الإنتاج باقية
- [Mirror Audit — Trace Not Claim](feedback_mirror_audit.md) — دقّق الـagents ونفسك بالـtrace الخام؛ الأفضلية للأرقام
- [Git Sync Workflow](git_sync_workflow.md) — جهازان: pull قبل، push بعد كل تغيير؛ main = Railway prod
- [🧱 maqalat: تحقّق من البناء قبل الدفع](feedback_maqalat_verify_before_push.md) — `npm run build` قبل أيّ push (لا `next build` وحده)؛ الـpre-push hook يفرضها؛ يمنع سلسلة ٥د-Vercel-Error التي كسرت ١٥ deploy متتالياً ٢٠٢٦-٠٩-١٣
- [🧱 الفهرسة مسؤولية المالك — لا مسؤوليّتي](feedback_indexing_is_owner_responsibility.md) — لا `index:ping` تلقائياً بعد أي تعديل؛ لا اقتراح الفهرسة كخطوة تالية؛ الاستثناء: طلب صريح

## ١) أسلوب العمل والتفضيلات (٢١)

- [🔥 ضبط حرق التوكنز](feedback_token_burn_control.md) — تكلفة الدور = المحادثة كلها؛ العدّاد في statusline · [Minimize Token Usage](feedback_minimize_token_usage.md) — مرجع سلبي: جلسة Maqalat
- [User Preferences](user_preferences.md) · [Analysis Style](feedback_analysis_style.md) — جداول مقارِنة تقود قراراً؛ أفعال وأكواد لا كلام ملمّع
- [Judge by Output](feedback_output_over_engineering.md) · [No Dead Code](feedback_no_dead_code.md) · [Regression Audit First](feedback_regression_audit.md) — diffs الأخيرة أولاً
- [Check .env First](feedback_check_env_first.md) · [Zero Friction Onboarding](feedback_zero_friction.md) — action-gated لا الدخول
- [Store Selection Criterion](feedback_store_selection.md) · [Prefer Codes over Tracking Links](feedback_prefer_codes_over_tracking_links.md) · [Never Publish Competing Codes](feedback_never_publish_competing_codes.md)
- [Always Publish When Done](feedback_always_publish.md) · [No Backticks in blog.ts](feedback_no_backticks_in_template_literals.md) — ``` يكسر SWC
- [AI Mastery Goal](user_ai_mastery_goal.md) — برومبت عالمي معاد الاستخدام؛ العقل المدبر: [البروتوكول](protocol_mastermind.md) · [البرومبت](mastermind_prompt.md)
- [Memory Sync via Junction](memory_sync_junction.md) · [☁️ Claude Code Cloud Sessions](claude_code_cloud_sessions.md) — يرثان الذاكرة بلا `.env`
- المهارات: [المثبَّتة](skills_install_manifest.md) (٢٩٦+٢٥ أمراً) · [عدّة التسويق](marketing_skills_toolkit.md) (١٧ skill)
- [Reconcile Web Repo Separately](reconcile_web_repo_separately.md) — dealpulseksa-web ريبو مستقل؛ افحصه أولاً

## ٢) البنية والتشغيل والنشر والموقع (١٩)

- أساسيات: [نظرة عامة](project_overview.md) · [الإعداد المحلي](setup_guide.md) · [سجلّ الإصلاحات](bug_fixes.md)
- Railway: [النشر](railway_deployment.md) · [عامل الجدولة](railway_scheduler_worker.md) (config منفصل، cron ≥5د)
- [Single Source of Truth](single_source_of_truth.md) — DB واحد + داشبورد واحد · [Platform Monitoring](platform_monitoring.md) — نشرات + تقرير صحة GSC
- [🔒 Security Hardening](security_hardening.md) — صفر ثغرة حرجة؛ /docs مقفول بالإنتاج
- متفرقات: [سعة البوت](bot_capacity_scaling.md) (~30/ث) · [ميزات مُنجَزة](project_completed_features.md) · [البريد](project_email_infrastructure.md) · [خطة الأسابيع](weeks_roadmap.md) · [معسكر ريادة](entrepreneur_bootcamp.md)
- الموقع: [المشروع](website_project.md) · [التصميم](website_design_preferences.md) · [محرّك السيو](website_seo_engine.md)
- [Web Repo Verification Recipes](web_repo_verification_recipes.md) + [Blog OOM/Client-Prop](web_blog_monolith_oom_and_client_prop_serialization.md) — tsconfig ضيّق يتجاوز OOM
- [⚡ جولة أداء الرئيسية](web_home_perf_pass.md) — TBT ٢٩٠٠→٢٠ms؛ اللائحة LCP وليس رافعة ترتيب
- [🎟️ Coupon Visual Identity](web_coupon_visual_identity.md) — `view=light` يرجّع الكود/الرابط `null`
- [🎫 Logo: Ticket + DP](brand_logo_ticket_2026_08.md) + [🎨 الهوية على الأسطح الأربعة](brand_identity_applied.md) — ملفّات الخط `-ar` مجزّأة

## ٣) قاعدة البيانات وموثوقية الأرقام (٩)

- [DB Foundation Audit](db_foundation_audit.md) — حيّ ٢٠٢٦-٠٨-٠٥: ٧١ جدول / ٣٨ فارغ / master ٥٢
- [master.store_id غير فريد](db_master_duplicate_store_id.md) · [المحلي منفصل عن الإنتاج](db_local_vs_railway.md)
- تتبّع/جغرافيا: [ثقة البيانات](data_trust_geo_device.md) (city/device مفبركة) · [قواعد تحليل المستخدمين](users_analytics_rules.md) · [Web Visits](web_visits_tracking.md)
- [Unified Favorites](unified_favorites.md) — SSOT + كتابة مزدوجة؛ الإزالة لا تُسجَّل
- [Bot-vs-Promo 3-Signal Check](bot_vs_promo_heuristic.md) · [Owned Audience Reality](owned_audience_reality.md) — ٥ بوت+١٠ ويب+صفر بثّ

## ٤) ميزات المنتج (١١)

- [🔎 طبقة البحث الذكي](search_intelligence_layer.md) — تطبيع عربي + `search_concepts` + `blog_bridge`؛ أعِد `--write` بعد أي تعديل مدوّنة
- ترند: [البنية النهائية](trend_architecture_final.md) · [source='all'](trend_source_all.md) · [Story System](story_system_design.md)
- [Support System](support_system.md) · [Publish Channels](publish_channels_feature.md) · [Season Reminders](season_reminders_feature.md)
- [Calendar Conversion Hub](calendar_conversion_hub.md) — كل موسم بوابة؛ «لا /en» يحكم الـURLs
- [Occasion Page Relevance Filter](occasion_page_relevance_filter.md) · [💳 التقسيط /installments](web_installments_bnpl.md)
- [🔐 جلسة الويب HttpOnly](web_session_httponly_cookie.md) · [🎯 صفّ صفقات تهمّك](web_home_interests_rail.md)
- [Web Login Gate Model](web_login_gate_model.md) · [Store Page Evergreen (404 Root Cause)](store_page_evergreen.md)

## ٥) التحليلات والسيو (٣٤)

- [🔮 Predictive/GEO Content Playbook](predictive_geo_content_playbook.md) — lead time ٣-٦ أشهر؛ صفر هَب /ramadan
- [🎯 منظومة إدارة الحملات](campaign_system.md) · [📈 GA4](web_ga4_install.md) `G-VRBHD0VK66`
- سيو خارجي: [فلتر النصائح](seo_external_advice_filter.md) (٧/١٠٠ مفيدة) · [مصادر التعلّم](seo_learning_sources.md)
- [🔤 تحقّق من تعريب البراند](seo_verify_brand_transliteration.md) — درس ناتشورال تاتش
- تحليل المتاجر: [الجناح](store_analytics_bi.md) · [إعادة البناء](analysis_rebuild_strategy.md) · [البنية النهائية](analytics_store_structure.md)
- كلمات مفتاحية: [⛔ Keyword Planner](google_ads_keyword_planner.md) (مرفوض) · [طلب السوق](keyword_demand_ksa.md) · [⚠️ Windsor GSC](windsor_gsc_connector.md) (أصفار وهمية)
- سلطة وفجوات: [Indexation Status](seo_indexation_status.md) (فهرسة 4→150) + [Deep Audit Fixes](seo_deep_audit_fixes.md) · [Authority Building](seo_authority_building.md) · [High-Demand Front](seo_high_demand_front_opened.md) · [Portfolio Verdict](seo_page_portfolio_verdict.md) (٧١٠/٧٦٤ صفر نقرة) · [Category Query Alignment](seo_category_query_alignment.md)
- [🤖 AI Citation Channel](ai_citation_channel.md) — ٤١٣ استشهاد Copilot · [🏫 عنقود الإدارة المدرسية](school_admin_cluster_engine.md) — ٣٤ مقالاً CTR١٠-٢٠٪
- تكاذُب: [/c/ ↔ /store](seo_c_store_cannibalization.md) · [Meta Code Leak](seo_meta_code_leak.md) · [⚖️ ثقة أدوات الفحص](seo_audit_tools_trust.md)
- الفهرسة: [حيّ](seo_google_indexing_live.md) (٢٠٠/يوم) · [الدفع بالجملة](seo_bulk_reindex_ops.md) · [الظهور لمحرّكات AI](seo_ai_visibility_optin.md)
- الترويج: [القنوات المملوكة](seo_owned_channels_pivot.md) · [PR Blitz Kit](seo_pr_blitz_kit.md) · [SaaSHub](saashub_directory_listing.md) (nofollow)
- الدومين: [خطة السلطة](domain_authority_plan.md) · [⚠️ فخّ الـcanonical](domain_canonical_trap.md) (dealpulesksa ميّت)
- [Content/Programmatic Strategy](content_programmatic_strategy.md) · [Seasonal School Bridge](seasonal_school_traffic_bridge.md) + [Competitor Landscape](competitor_landscape.md)
- [🔌 Claude SEO Plugin](claude_seo_plugin.md) — ١٨ agent+٢٥ skill؛ السحابة محجوبة عن الموقع
- مصادر أوّلية: [🏺 قصر الاواني](qasr_alawani_source_of_truth.md) + [🚕 لائحة نقل الركاب](ride_hailing_regulation_sources.md)

## ٦) المحتوى والمدوّنة (٢٩)

- [Voice Bible](voice_bible.md) · [Blog Total = Count It Live](blog_massive_content_session.md) — عُدّ حيّاً، لا تجمع تقديرياً
- [✅ ١٧١ مقالاً هزيلاً — صفر متبقٍّ](blog_thin_content_rewrite_2026_09.md) · [✅ FAQ لكل مقال — صفر متبقٍّ من ٢٠٤٢](blog_faq_sections_completion_2026_09.md) — كلاهما من تدقيق ٢٣٠٦ صفحة، سكريبتات scratch للتحقّق الحيّ
- عناقيد عطور وعناية (YMYL جزئي): [ذي بيوتي سيكرتس](blog_beautysecrets_cluster.md)(٢٢) · [بلوار](blog_beluar_cluster.md)(١٦) · [ريف](blog_reef_cluster.md)(١٨) · [رسيس](blog_rasees_cluster.md)(١٦) · [ناتشورال تاتش](blog_naturaltouch_cluster.md)(١٦، ٤٢ صفحة `/c/` ميتة) · [الماجد للعود](blog_almajed_cluster.md)(١٥) · [فيرنز اند بيتل](blog_fnp_cluster.md)(١٦) · [الدخيل للعود](blog_aldakheel_cluster.md)(١٦)
- عناقيد أزياء وتجزئة: [فاشون.سا](blog_fashion_cluster.md)(٢٠، زي مدرسي ٤ مدارس) · [ليفل شوز](blog_levelshoes_cluster.md)(٢٠) · [ماكس فاشن+بوما+مودانيسا+روملس](blog_maxfashion_puma_clusters.md)(٦٨، مواقعها محجوبة للبوتات)
- عناقيد أخرى: [يمّك](blog_yammak_cluster.md)(٢٠، خدمات لا منتجات) · [بتيل](blog_bateel_cluster.md)(١٨) · [ممزورلد](blog_mumzworld_cluster.md)(٢٠، YMYL) · [صيدلية النهدي](blog_nahdi_cluster.md)(٢٠، YMYL صارم) · [نايس](blog_nice_cluster.md)(٢٣، ⚠️ ≠نايس ون) · [دبدوب](blog_dabdoob_cluster.md)(١٧، ⚠️ تلوّث SERP)
- [✈️ المطار للسفر](blog_almatar_travel_cluster.md) — ٤٤ مقالاً (أكبر عنقود)؛ صفر رقم ريال مفبرك
- `blog_bridge` أُعيد بناؤه ٢٠٢٦-٠٩-٠٩: ١٥٦٩ صفّاً/٧٠ متجراً · الصحّة: [عنقود المكمّلات](health_content_cluster.md) · [مصادر الاستشهاد](health_citation_sourcing.md)
- [Blog Internal-Link De-orphan](blog_internal_link_deorphan.md) — 65 مقال يتيم صُفِّرت · [Inline Code Chips](blog_inline_code_chips.md) + [Jolina Angle](jolina_prepurchase_angle.md)
- عناقيد كبرى: [١٤ متجر/٢٨٠](blog_14clusters_july11.md) · [٧ عناقيد/١٠٥](blog_7clusters_july11.md) · [AliExpress ١٥٠](blog_aliexpress_cluster.md) · [ألعاب ١٠/٧٢](blog_toys_cluster_progress.md)
- [💇 نزيه — ست ممرّات فارغة](blog_nazih_cluster.md) — لا تغزُ عنقود شريك
- عناقيد متاجر (١٢–١٩ مقالاً لكلٍّ): [ذا ديل](blog_thedeal_cluster.md) · [فوغا كلوسيت](blog_vogacloset_cluster.md) · [ماماز](blog_mamaspapas_cluster.md) · [H&M](blog_hm_cluster.md) · [بيد إن روم](blog_bedinroom_cluster.md) · [لحظات القهوة](blog_lahazat_cluster.md) · [جنى العسل](blog_jana_honey_cluster.md) · [عبدالصمد القرشي](blog_asq_cluster.md) · [⚠️ أثاث المنزل](blog_home_furniture_cluster.md)

## ٧) قنوات الأفلييت والشراكات (١٢)

- سلة: [القناة](salla_affiliate_channel.md) · [الإسناد بالكود](salla_orders_attribution_reality.md) · [٦ متاجر محوِّلة](salla_proven_converters.md)
- Admitad: [الإعداد](admitad_affiliate_setup.md) · [حجب ISP](admitad_dns_block.md)
- شبكات أخرى: [CodeMap](codemap_affiliate_channel.md) · [Boostiny](boostiny_publisher_channel.md) · [DCM](dcm_network_channel.md) · [Zid](zid_affiliate_channel.md)
- [Jahez Direct BD](jahez_direct_bd.md) · [📄 الملف التعريفي](company_profile_bilingual.md) (AR+EN)
- [Affiliate PPC Brand Restrictions](affiliate_ppc_brand_restrictions.md) · [Contact Emails](contact_emails.md)

## ٨) التسويق والسوشيال (٦)

- [Marketing Baseline & Strategy](marketing_baseline_and_strategy.md) — محرّكا الكسب: المواسم + الإدارة المدرسية
- انستقرام: [محرّك المحتوى](instagram_content_engine.md) · [محرّك النمو](ig_growth_engine.md) · [سياسة النشر](ig_publish_policy.md)
- [Brand Face for Flow Reels](brand_face_reels.md) · [Social Listening Deferred](social_listening_deferred.md) · [Local TTS (REMOVED)](tts_engine_xtts_v2.md)

## ٩) مشروع مقالات (Maqalat.org) — مستقل تماماً عن نبض الصفقات

> [عزل تام إلزامي](feedback_maqalat_isolation.md): ريبو وحساب Cloudflare منفصلان.

- [🆕 نظرة عامة](project_maqalat.md) · [الميثاق التحريري](project_maqalat_editorial_charter.md) + [دليل الكتابة](project_maqalat_writing_playbook.md)
- [سياسات AdSense ٢٠٢٦](project_maqalat_adsense_policies.md) · [عدّة السكلز](project_maqalat_toolkit.md) · [مسح ١٣٠ منافساً](project_maqalat_competitor_landscape.md)
- عناقيد: [AI](project_maqalat_ai_cluster.md)(~١٥٠) · [الجامعات](project_maqalat_universities_cluster.md)(٢٠) · [الخدمات الحكومية](project_maqalat_government_cluster.md)(٣٠+حاسبة)
- [تدقيق ٠٩-٠٢](project_maqalat_audit_2026_09_02.md) · [Indexing API](project_maqalat_indexing_api.md) (٢٠٠/٢٠٠) · [🎯 AdSense Readiness](project_maqalat_adsense_readiness.md)
- مطبّات تقنية: [٣ أنماط عربية تكسر MDX](project_maqalat_mdx_pitfalls.md) · [MDX v3 `{/* */}`](feedback_mdx_v3_comments.md) · [٣ مطبّات @vercel/og](project_maqalat_og_pitfalls.md)
- [ثنائية اللغة](project_maqalat_i18n.md) · [لوحة /admin](project_maqalat_admin_dashboard.md) · [النشرة البريدية](project_maqalat_newsletter.md)
- [⚠️ Git auth محجوز](project_maqalat_git_auth.md) — الحلّ PAT inline بالرابط

### صيانة الفهرس — كل ملف على القرص يجب أن يظهر هنا

```powershell
$idx=(Get-Content Claude_Memory\MEMORY.md -Encoding UTF8|%{[regex]::Matches($_,'\(([^)]+\.md)\)')|%{$_.Groups[1].Value}})
(Get-ChildItem Claude_Memory -Filter *.md|?{$_.Name -ne 'MEMORY.md'}).Name|?{$idx -notcontains $_}
```
