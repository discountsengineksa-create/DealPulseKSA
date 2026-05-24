-- ============================================================================
-- Migration 017 — Drop dead columns from social_responses
-- ============================================================================
-- في خطة Week 7-8 الأصلية، كان يُفترض أن تُعبَّأ هذه الأعمدة عبر:
--   • engagement_json      → webhook من المنصات بإحصاءات (likes/replies)
--   • affiliate_clicks     → tracking pixel على الرد
--   • revenue_attributed_usd → attribution logic ربط البيع بالرد
--
-- الواقع: لا webhook، لا pixel، لا attribution. الأعمدة بقيت NULL لكل سطر
-- منذ أسبوعين. حذفها:
--   1. يقلّل حجم الجدول (مفيد للسرعة عند الـ COUNT/SELECT)
--   2. يمنع كتابة تقارير بأرقام مزيّفة (دائماً صفر)
--   3. ينظّف الـ schema documentation
--
-- لو احتجت تتبّع revenue لاحقاً عبر اتفاقية attribution مع الشبكات،
-- ستعود الأعمدة بـ migration جديدة وقتها.
-- ============================================================================

BEGIN;

-- نتأكد من وجود الأعمدة قبل الحذف (آمن للتشغيل المتعدد)
ALTER TABLE social_responses
    DROP COLUMN IF EXISTS engagement_json,
    DROP COLUMN IF EXISTS affiliate_clicks,
    DROP COLUMN IF EXISTS revenue_attributed_usd;

-- نسجّل التنظيف في سجل التدقيق (لو الجدول موجود)
INSERT INTO pdpl_audit_log (actor, action, target, status, meta)
SELECT 'system', 'schema_cleanup', 'social_responses', 'ok',
       jsonb_build_object(
         'dropped_columns', ARRAY['engagement_json', 'affiliate_clicks', 'revenue_attributed_usd'],
         'reason', 'Never populated since Week 8 — no webhook/pixel/attribution exists'
       )
WHERE EXISTS (SELECT 1 FROM information_schema.tables
              WHERE table_name = 'pdpl_audit_log');

COMMIT;
