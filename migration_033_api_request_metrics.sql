-- Migration 033: api_request_metrics — مراقبة أداء الموقع (زمن الاستجابة + الأخطاء)
-- Run once: psql "$DATABASE_URL" -f migration_033_api_request_metrics.sql
-- Safe to re-run (IF NOT EXISTS).
--
-- يملؤه middleware في bot_app.py عبر buffer + flusher (api/utils/request_metrics.py).
-- الجدول يُنشأ تلقائياً عند أول كبسة أيضاً، فهذا الملف للتوثيق/الإنشاء المبكر.
-- الاحتفاظ: يحذف الـ flusher الصفوف الأقدم من 7 أيام كل ساعة.

BEGIN;

CREATE TABLE IF NOT EXISTS api_request_metrics (
    id          BIGSERIAL   PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    method      VARCHAR(8),
    path        TEXT,                                -- منمَّط: {id}/{slug} لتقليل التنوّع
    status_code SMALLINT,
    latency_ms  INTEGER
);

COMMENT ON TABLE api_request_metrics IS
    'مقياس أداء لكل طلب API — زمن الاستجابة وكود الحالة. للكشف عن البطء/التعليق/الأخطاء.';

CREATE INDEX IF NOT EXISTS idx_api_metrics_created
    ON api_request_metrics (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_metrics_errors
    ON api_request_metrics (created_at DESC)
    WHERE status_code >= 500;

COMMIT;
