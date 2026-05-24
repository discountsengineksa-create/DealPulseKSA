-- ============================================================================
-- Migration 018 — Social Leads Radar (VIEW على social_signals الموجود)
-- ============================================================================
-- لا ننشئ جدولاً جديداً. نستخدم social_signals (موجود من migration_015) لأنه:
--   ✓ يحتوي كل الأعمدة المطلوبة: platform, author_handle, content, source_url,
--     candidate_master_ids
--   ✓ مأهول تلقائياً من api/social_listener/pollers.py كل 10 دقائق
--   ✓ مفهرس + dedup شغّال
--
-- ما نضيفه:
--   1. حالات جديدة لـ social_signals.status:
--        'lead_pending'      → تمت مطابقته بمتجر، ينتظر ردك اليدوي
--        'lead_replied'      → ضغطت "تم الرد" في الداشبورد
--        'lead_dismissed'    → أنت قرّرت تجاهله (لا تريد الرد)
--
--   2. View v_social_leads → يقدّم البيانات بشكل قابل للعرض مباشرة في
--      الداشبورد (يستخرج اسم المتجر من JOIN على master)
--
-- ملاحظة على الـ status flow الحالي:
--   responder.py حالياً يستخدم: new → scored → matched → responded → ignored
--   نُبقي هذه (للتوافق) ونضيف فوقها lead_* للحالات المُعالَجة من الداشبورد.
-- ============================================================================

BEGIN;

-- 1) لا حاجة لـ ALTER TABLE — status هو VARCHAR(20) بدون CHECK constraint
--    لذا أي قيمة نصية مقبولة. مجرد convention جديد.

-- 2) View للـ leads — يجمع كل اللي يحتاج تدخّل بشري
CREATE OR REPLACE VIEW v_social_leads AS
SELECT
    s.id                                    AS lead_id,
    s.platform                              AS platform,
    COALESCE(s.author_handle, '—')          AS username,
    s.content                               AS post_text,
    s.source_url                            AS post_url,
    s.intent_score                          AS intent_score,
    s.candidate_master_ids                  AS candidate_master_ids,
    COALESCE(NULLIF(m.name_en, ''), m.store_id, '—') AS target_store,
    m.store_id                              AS target_store_id,
    m.cloaked_slug                          AS target_cloaked_slug,
    s.status                                AS status,
    s.captured_at                           AS captured_at,
    EXTRACT(EPOCH FROM (NOW() - s.captured_at))::int  AS age_seconds
FROM social_signals s
LEFT JOIN LATERAL (
    -- نأخذ أول candidate_master_id لاستخراج اسم المتجر
    SELECT m1.store_id, m1.name_en, m1.cloaked_slug
    FROM master m1
    WHERE s.candidate_master_ids IS NOT NULL
      AND array_length(s.candidate_master_ids, 1) > 0
      AND m1.id = s.candidate_master_ids[1]
    LIMIT 1
) m ON TRUE
WHERE s.status IN ('matched', 'responded', 'lead_pending', 'lead_replied', 'lead_dismissed');

COMMENT ON VIEW v_social_leads IS
    'Social leads radar — يجمع mentions من Reddit/Google Alerts/إلخ ويربطها بمتاجرنا. '
    'يستخدمه الداشبورد لعرض شاشة "الرد اليدوي" التي يضغط فيها الأدمن "↗ افتح" و "✅ تم".';

-- 3) فهرس مفيد لتسريع استعلام "الأحدث pending أولاً"
CREATE INDEX IF NOT EXISTS idx_social_signals_lead_status
    ON social_signals(captured_at DESC)
    WHERE status IN ('matched', 'responded', 'lead_pending');

-- 4) لو في PDPL audit موجود، نسجّل
INSERT INTO pdpl_audit_log (actor, action, target, status, meta)
SELECT 'system', 'migration_applied', 'migration_018', 'ok',
       jsonb_build_object('feature', 'social_leads_radar_view')
WHERE EXISTS (SELECT 1 FROM information_schema.tables
              WHERE table_name = 'pdpl_audit_log');

COMMIT;

-- اختبار سريع — بعد التشغيل، شغّل هذا للتحقق:
-- SELECT lead_id, platform, username, target_store, status, age_seconds
-- FROM v_social_leads ORDER BY captured_at DESC LIMIT 10;
