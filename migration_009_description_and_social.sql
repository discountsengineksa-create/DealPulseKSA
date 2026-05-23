-- Migration 009: Description column + Social Posts Log
-- Run once: psql "$DATABASE_URL" -f migration_009_description_and_social.sql

-- 1) عمود تفاصيل العرض الجديد — يُستخدم في قالب البث على منصات السوشيال
ALTER TABLE master ADD COLUMN IF NOT EXISTS description TEXT;

COMMENT ON COLUMN master.description IS
    'نص تفاصيل العرض المنشور على منصات السوشيال — يُستخدم في قالب البث الموحّد';

-- 2) جدول تسجيل محاولات النشر لكل منصة
CREATE TABLE IF NOT EXISTS social_posts_log (
    id               SERIAL PRIMARY KEY,
    master_id        INTEGER REFERENCES master(id) ON DELETE CASCADE,
    store_id         TEXT NOT NULL,
    platform         TEXT NOT NULL,
        -- 'x' | 'instagram' | 'facebook' | 'pinterest' | 'telegram' | 'discord' | 'threads' | 'linkedin'
    post_text        TEXT NOT NULL,
    image_url        TEXT,
    status           TEXT NOT NULL DEFAULT 'queued',
        -- 'queued' | 'sent' | 'failed' | 'skipped'
    platform_post_id TEXT,
    error_message    TEXT,
    attempted_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_social_posts_log_master_id
    ON social_posts_log (master_id);

CREATE INDEX IF NOT EXISTS idx_social_posts_log_platform_status
    ON social_posts_log (platform, status);

CREATE INDEX IF NOT EXISTS idx_social_posts_log_attempted_at
    ON social_posts_log (attempted_at DESC);
