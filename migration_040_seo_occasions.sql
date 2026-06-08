-- ════════════════════════════════════════════════════════════════════════════
-- Migration 040: مناسبات SEO بتاريخ حقيقي (DATE) + بذرة مناسبات السعودية 2026
-- ════════════════════════════════════════════════════════════════════════════
-- لماذا: محرّك SEO الأوتوماتيكي يربط المتاجر بمناسبة سعودية قادمة خلال أسبوعين.
--        العمود القديم seasonal_events.event_date نصّي (TEXT) → غير موثوق للحساب.
--        نضيف occasion_date DATE ويديره المالك من «مدير المناسبات» بالداشبورد.
--
-- التطبيق:  python api/run_migration.py migration_040_seo_occasions.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE seasonal_events
    ADD COLUMN IF NOT EXISTS occasion_date DATE;

COMMENT ON COLUMN seasonal_events.occasion_date IS
    'تاريخ المناسبة (DATE) — يستخدمه محرّك SEO للربط خلال نافذة أسبوعين. يُدار من الداشبورد.';

-- بذرة مناسبات السعودية 2026 (تقديرية للمناسبات الهجرية — المالك يعدّلها من الواجهة)
INSERT INTO seasonal_events (event_name, occasion_date, event_date, bot_status)
SELECT v.name, v.d, v.d::text, 'انتظار'
FROM (VALUES
    ('رمضان',                 DATE '2026-02-18'),
    ('يوم التأسيس',           DATE '2026-02-22'),
    ('عيد الفطر',             DATE '2026-03-20'),
    ('عيد الأضحى',            DATE '2026-05-27'),
    ('تخفيضات الصيف',         DATE '2026-06-15'),
    ('العودة للمدارس',        DATE '2026-08-23'),
    ('اليوم الوطني السعودي',  DATE '2026-09-23'),
    ('يوم العزّاب 11.11',     DATE '2026-11-11'),
    ('الجمعة البيضاء',        DATE '2026-11-27'),
    ('رأس السنة',             DATE '2026-12-31')
) AS v(name, d)
WHERE NOT EXISTS (
    SELECT 1 FROM seasonal_events s WHERE s.event_name = v.name
);

COMMIT;
