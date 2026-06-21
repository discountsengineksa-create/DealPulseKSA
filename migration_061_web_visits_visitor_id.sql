-- ════════════════════════════════════════════════════════════════════════════
-- Migration 061: بصمة زائر ثابتة (web_visits.visitor_id) — تمييز العائدين
-- ════════════════════════════════════════════════════════════════════════════
-- visit_id = معرّف الجلسة (sessionStorage، يتغيّر كل جلسة). لا يكفي للإجابة على
-- «هل نفس الشخص دخل أكثر من مرة» لأن كل جلسة = صف جديد بلا رابط بينها.
-- visitor_id = معرّف متصفّح دائم (localStorage)، يبقى عبر الجلسات والأيام حتى لو
-- تغيّر الـ IP (شبكات الجوال تبدّله) — فنربط زيارات نفس الزائر المجهول.
-- بلا أي بيانات شخصية (UUID عشوائي) → White-Hat ومتوافق خصوصياً.
--
-- الهوية في الداشبورد بالأولوية: user_id (مسجّل) ← visitor_id (مجهول معروف) ← ip_hash.
-- الصفوف القديمة (قبل هذا) visitor_id = NULL → يقع على ip_hash تلقائياً.
--
-- التطبيق:  python api/run_migration.py migration_061_web_visits_visitor_id.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE web_visits ADD COLUMN IF NOT EXISTS visitor_id UUID;

-- تجميع زيارات نفس الزائر (GROUP BY/DISTINCT) — جزئي لتجاهل الصفوف بلا بصمة.
CREATE INDEX IF NOT EXISTS idx_web_visits_visitor
    ON web_visits (visitor_id) WHERE visitor_id IS NOT NULL;

COMMIT;
