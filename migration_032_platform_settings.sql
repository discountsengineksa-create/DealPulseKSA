-- Migration 032: platform_settings — مفتاح/قيمة لإعدادات وقت التشغيل
-- Run once: psql "$DATABASE_URL" -f migration_032_platform_settings.sql
-- Safe to re-run (IF NOT EXISTS).
--
-- الغرض: ضوابط يقرأها العمّال (workers) في كل دورة بدون إعادة نشر Railway.
-- تُدار من صفحة «متابعة المنصة» في الداشبورد. المفاتيح المستخدمة حالياً:
--   directive_enabled    '1' | '0'   — مفتاح تشغيل/إيقاف مولّد التوجيهات
--   directive_min_hours  عدد ساعات    — أقل فاصل بين إيميلين (0 = بلا تقييد)
--   directive_recipient  بريد         — يتجاوز OPS_ALERT_EMAIL (فارغ = الافتراضي)

BEGIN;

CREATE TABLE IF NOT EXISTS platform_settings (
    key         VARCHAR(60)  PRIMARY KEY,
    value       TEXT,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_by  VARCHAR(80)
);

COMMENT ON TABLE platform_settings IS
    'مفتاح/قيمة لإعدادات وقت التشغيل التي يحترمها العمّال (workers) بدون إعادة نشر. تُدار من صفحة «متابعة المنصة».';

COMMIT;
