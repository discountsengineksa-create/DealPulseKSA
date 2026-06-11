-- migration_049_drop_abandoned_feature_tables.sql
-- تنظيف (2026-06-11): حذف جداول ميزات تخلّى عنها المستخدم + جداول مُستبدَلة ميتة.
--
-- كلها مؤكَّدة آمنة (تحقّقنا): 0 صف · لا FK يشير لها · لا view يعتمد عليها · غير
-- مرجوعة في أي كود حيّ. فارغة → لا حاجة لنسخة احتياطية. idempotent عبر IF EXISTS.
--
-- ملاحظة: llm_semantic_cache (v1) لم يُحذف رغم وجود v2 — فيه صف فعلي ويُرجَع في الكود؛
--          يلزم نقل مراجعه إلى llm_semantic_cache_v2 أولاً (خطوة لاحقة).

BEGIN;

-- ميزات تخلّى عنها المستخدم
DROP TABLE IF EXISTS channel_ads_queue;   -- ناشر القناة
DROP TABLE IF EXISTS flash_offers_queue;  -- العروض الخاطفة
DROP TABLE IF EXISTS franchise_agents;    -- الامتياز/الوكلاء
DROP TABLE IF EXISTS loyalty_history;     -- نظام الولاء
DROP TABLE IF EXISTS loyalty_settings;    -- نظام الولاء

-- جداول مُستبدَلة/ميتة
DROP TABLE IF EXISTS search_analytics;    -- مُستبدَل بـ direct_search (النشط)
DROP TABLE IF EXISTS app_monitor;         -- مُستبدَل بـ api_request_metrics + منظومة المتابعة
DROP TABLE IF EXISTS traffic_sources;     -- غير مستخدَم
DROP TABLE IF EXISTS user_preferences;    -- غير مستخدَم

COMMIT;
