-- ════════════════════════════════════════════════════════════════════════════
-- Migration 002: Web Platform Support (Auth + Tracking + Favorites)
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف دعم موقع dealpulseksa.com:
--   1. عمود source على action_logs للتمييز بين البوت والموقع
--   2. جدول web_users لمستخدمي الموقع المسجّلين برقم الجوال
--   3. الموقع يستخدم direct_search.platform='Web' (موجود مسبقاً)
-- ════════════════════════════════════════════════════════════════════════════

-- ─── 1. إضافة source على action_logs ──────────────────────────────────────
ALTER TABLE action_logs
    ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'bot';

-- نُحدّث السجلات القديمة لتكون 'bot' بشكل صريح
UPDATE action_logs SET source = 'bot' WHERE source IS NULL;

-- index للاستعلامات اللي تفصل البوت عن الموقع
CREATE INDEX IF NOT EXISTS idx_action_logs_source ON action_logs(source);

-- ─── 2. جدول web_users — مستخدمي الموقع ──────────────────────────────────
CREATE TABLE IF NOT EXISTS web_users (
    id                     BIGSERIAL PRIMARY KEY,
    phone_number           TEXT NOT NULL UNIQUE,
    firebase_uid           TEXT UNIQUE,
    display_name           TEXT,
    email                  TEXT,
    country                TEXT DEFAULT 'SA',
    city                   TEXT,
    lang                   TEXT DEFAULT 'ar',
    created_at             TIMESTAMP DEFAULT NOW(),
    last_seen              TIMESTAMP DEFAULT NOW(),
    status                 TEXT DEFAULT 'Active',
    -- نفس بنية bot_users للتوحيد:
    manual_favorites       TEXT[] DEFAULT '{}',
    copied_coupons_history TEXT[] DEFAULT '{}',
    interests              TEXT[] DEFAULT '{}',
    visited_clicks         INTEGER DEFAULT 0,
    store_copy_count       INTEGER DEFAULT 0,
    device_type            TEXT,
    user_agent             TEXT,
    -- IP للأمان وكشف الـ abuse
    last_ip                INET
);

CREATE INDEX IF NOT EXISTS idx_web_users_phone        ON web_users(phone_number);
CREATE INDEX IF NOT EXISTS idx_web_users_firebase_uid ON web_users(firebase_uid);
CREATE INDEX IF NOT EXISTS idx_web_users_last_seen    ON web_users(last_seen);

-- ─── 3. تأكد أن direct_search جاهز للموقع ──────────────────────────────
-- platform='Web' للبحث من الموقع، 'Bot' للبوت، 'Dashboard' للـ admin
-- لا يحتاج تعديل، لكن نضيف index للأداء
CREATE INDEX IF NOT EXISTS idx_direct_search_platform ON direct_search(platform);

-- ─── ✅ Done ─────────────────────────────────────────────────────────────
-- بعد هذه الـ migration:
--   action_logs : يدعم 'bot' و 'web' و 'dashboard'
--   web_users   : جاهز لمستخدمي الموقع
--   direct_search: يدعم platform='Web' عبر API
