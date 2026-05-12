-- migration_007_email_logs.sql
-- إنشاء جدول سجلات الحملات البريدية

CREATE TABLE IF NOT EXISTS email_logs (
    id              SERIAL PRIMARY KEY,
    subject         TEXT         NOT NULL,
    body_html       TEXT,
    banner_url      TEXT,
    target_audience TEXT         DEFAULT 'الكل',
    delivery_count  INTEGER      DEFAULT 0,
    sent_count      INTEGER      DEFAULT 0,
    failed_count    INTEGER      DEFAULT 0,
    status          TEXT         DEFAULT 'completed',  -- completed | partial | failed
    sent_by         TEXT         DEFAULT 'dashboard',
    sent_at         TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at ON email_logs (sent_at DESC);
