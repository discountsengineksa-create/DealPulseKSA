-- ════════════════════════════════════════════════════════════════════════════
-- Migration 062: هوية الزائر المجهول على كل الحركات (action_logs.visitor_id)
-- ════════════════════════════════════════════════════════════════════════════
-- الهدف: الموقع مفتوح للجميع بلا إجبار تسجيل (لكسب الترافيك)، ومع ذلك نريد
-- متابعة كل حركة (نسخ/نقر/بحث/مشاهدة/ترند) منسوبةً لهوية ثابتة حتى للمجهول.
--
-- اليوم action_logs.user_id = NULL لكل حركة من زائر غير مسجّل → حركاته بلا رابط.
-- نضيف visitor_id (نفس بصمة web_visits.visitor_id من localStorage) فتُنسب كل
-- حركاته لنفس الهوية، ونربط زيارته بسلوكه (نسخ/بحث/مشاهدة).
--
-- البوت/الميني لا يرسلانه (لهم telegram_id في user_id) → NULL لصفوفهم، سليم.
-- الهوية في التحليلات بالأولوية: user_id ← visitor_id ← ip_hash.
--
-- التطبيق:  python api/run_migration.py migration_062_action_logs_visitor_id.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS visitor_id UUID;

-- تجميع حركات نفس الزائر المجهول (GROUP BY/JOIN) — جزئي لتجاهل صفوف البوت/المسجّل.
CREATE INDEX IF NOT EXISTS idx_action_logs_visitor
    ON action_logs (visitor_id) WHERE visitor_id IS NOT NULL;

COMMIT;
