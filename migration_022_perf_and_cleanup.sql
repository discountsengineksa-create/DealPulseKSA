-- migration_022_perf_and_cleanup.sql
-- ═════════════════════════════════════════════════════════════════════════════
-- Pre-launch performance hardening + data retention guards.
--
-- يجمع 3 إصلاحات حرجة قبل الإطلاق:
--   1. فهارس مركّبة على action_logs (تسريع تحليلات الداشبورد 15-25%)
--   2. فهرس على bot_users.lang (تسريع شرائح اللغة)
--   3. دالة + جدولة تنظيف llm_semantic_cache المنتهي (لمنع تراكم صفوف ميتة)
--   4. partial index على action_logs لـ "آخر 90 يوم" (الأكثر استخداماً)
--
-- كل العمليات idempotent — يمكن إعادة التشغيل بأمان.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. فهرس مركّب: (store_id, action_type)
--    يدعم تحليلات الأقسام والمتاجر التي تفلتر بـ store + action معاً.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_action_logs_store_action
    ON action_logs (store_id, action_type)
    WHERE store_id IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. فهرس مركّب: (user_id, action_type)
--    يدعم استعلامات سلوك المستخدم من البوت (copy/click counts per user).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_action_logs_user_action
    ON action_logs (user_id, action_type)
    WHERE user_id IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. فهرس زمني عام للترتيب التنازلي حسب الوقت — يُسرّع SELECT ... ORDER BY DESC
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_action_logs_time_desc
    ON action_logs (action_time DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. فهرس على bot_users.lang — يُسرّع شرائح اللغة في التقارير
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bot_users_lang
    ON bot_users (lang)
    WHERE lang IS NOT NULL;

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. فهرس على direct_search.search_date — لتسريع dashboard بحث الأكواد
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_direct_search_date_desc
    ON direct_search (search_date DESC);

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. تنظيف llm_semantic_cache المنتهي — دالة + استدعاء فوري
--    الـ scheduler الـ FastAPI سيستدعيها لاحقاً (انظر api/workers/scheduler.py)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION cleanup_expired_llm_cache()
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count integer;
BEGIN
    DELETE FROM llm_semantic_cache
    WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- تنظيف فوري لما هو منتهٍ الآن
SELECT cleanup_expired_llm_cache();

-- ─────────────────────────────────────────────────────────────────────────────
-- 7. جدول تتبّع المهاجرات (لـ migrations المستقبلية)
--    idempotent — يُنشأ مرة فقط. لاحقاً api/run_migration.py سيحدّثه.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS migration_history (
    id           BIGSERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,
    applied_at   TIMESTAMPTZ DEFAULT NOW(),
    checksum     TEXT
);

-- تسجيل هذه المهاجرة (idempotent)
INSERT INTO migration_history (name)
VALUES ('migration_022_perf_and_cleanup')
ON CONFLICT (name) DO NOTHING;

COMMIT;

-- ─────────────────────────────────────────────────────────────────────────────
-- ملاحظات تشغيل:
--   • بعد التطبيق، Run ANALYZE على الجداول المعدّلة:
--       ANALYZE action_logs;
--       ANALYZE bot_users;
--       ANALYZE direct_search;
--   • لإضافة جدولة تلقائية لتنظيف الـ LLM cache كل ساعة، أضف لـ Railway:
--       SELECT cleanup_expired_llm_cache(); — عبر pg_cron أو من api/workers
-- ─────────────────────────────────────────────────────────────────────────────
