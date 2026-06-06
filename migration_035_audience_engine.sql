-- ════════════════════════════════════════════════════════════════════════════
-- Migration 035: Audience Engine — بنية الشرائح والإرسال
-- ════════════════════════════════════════════════════════════════════════════
-- يبني بنية كاملة لـ Segment Builder:
--   • audience_segments         — تعريف الشريحة (JSONB rules tree)
--   • audience_segment_versions — تاريخ تعديل الشرائح (rollback)
--   • broadcast_recipients      — تتبّع كل مستلم على حدة (نجح/فشل/فُتح)
--   • broadcast_exclusions      — قائمة استثناء يدوية (don't-send list)
--   • broadcast_schedules       — حملات مجدولة (cron-like)
-- ويضيف أعمدة لربط broadcast_logs و email_logs بالشريحة المستخدمة.
-- يُضيف Indexes للأداء على الاستعلامات الثقيلة.
--
-- التطبيق: python api/run_migration.py migration_035_audience_engine.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. الشرائح المحفوظة ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audience_segments (
    id              SERIAL      PRIMARY KEY,
    name            TEXT        NOT NULL,
    description     TEXT,
    rules_json      JSONB       NOT NULL,           -- شجرة المجموعات/القواعد
    channel         TEXT        CHECK (channel IN ('telegram','email','both') OR channel IS NULL),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    use_count       INT         DEFAULT 0,
    last_count      INT,                            -- آخر عدّ محفوظ (للسرعة)
    last_count_at   TIMESTAMPTZ,
    created_by      TEXT,
    is_template     BOOLEAN     DEFAULT FALSE       -- TRUE = قالب جاهز
);
CREATE INDEX IF NOT EXISTS idx_segments_channel    ON audience_segments (channel);
CREATE INDEX IF NOT EXISTS idx_segments_last_used  ON audience_segments (last_used_at DESC);
CREATE INDEX IF NOT EXISTS idx_segments_template   ON audience_segments (is_template) WHERE is_template = TRUE;

COMMENT ON COLUMN audience_segments.rules_json IS
    'شجرة JSON: {version, logic: or, groups: [{logic: and, rules: [...]}]}';
COMMENT ON COLUMN audience_segments.last_count IS
    'آخر عدّ مطابقين. ممكن يقدم — last_count_at يخبرك متى. للعرض السريع فقط، الإرسال يعيد العدّ.';

-- ─── 2. نسخ تاريخية للشرائح (rollback) ────────────────────────────────────
CREATE TABLE IF NOT EXISTS audience_segment_versions (
    id              SERIAL      PRIMARY KEY,
    segment_id      INT         REFERENCES audience_segments(id) ON DELETE CASCADE,
    rules_json      JSONB       NOT NULL,
    saved_at        TIMESTAMPTZ DEFAULT NOW(),
    saved_by        TEXT,
    change_note     TEXT
);
CREATE INDEX IF NOT EXISTS idx_segment_versions_segment ON audience_segment_versions (segment_id, saved_at DESC);

-- ─── 3. تتبّع كل مستلم على حدة ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS broadcast_recipients (
    id              BIGSERIAL   PRIMARY KEY,
    broadcast_id    INT         NOT NULL,                -- ربط بـ broadcast_logs أو email_logs
    broadcast_kind  TEXT        NOT NULL CHECK (broadcast_kind IN ('telegram','email')),
    user_identifier TEXT        NOT NULL,                -- telegram_id أو email
    user_db_id      TEXT,                                -- bot_users.telegram_id أو web_users.id
    queued_at       TIMESTAMPTZ DEFAULT NOW(),
    sent_at         TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'queued'
                    CHECK (status IN ('queued','sending','sent','failed','skipped','opened','clicked')),
    error_message   TEXT,
    opened_at       TIMESTAMPTZ,                         -- البريد فقط (إن توفّر tracking)
    variant         TEXT                                  -- 'A' أو 'B' لاختبار A/B
);
CREATE INDEX IF NOT EXISTS idx_recipients_broadcast ON broadcast_recipients (broadcast_id, broadcast_kind);
CREATE INDEX IF NOT EXISTS idx_recipients_user      ON broadcast_recipients (user_identifier, sent_at DESC);
CREATE INDEX IF NOT EXISTS idx_recipients_status    ON broadcast_recipients (status, queued_at) WHERE status IN ('queued','sending');

-- ─── 4. قائمة استثناء يدوية ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS broadcast_exclusions (
    id              SERIAL      PRIMARY KEY,
    channel         TEXT        NOT NULL CHECK (channel IN ('telegram','email','both')),
    user_identifier TEXT        NOT NULL,
    reason          TEXT,
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    added_by        TEXT,
    UNIQUE (channel, user_identifier)
);
CREATE INDEX IF NOT EXISTS idx_exclusions_lookup ON broadcast_exclusions (user_identifier, channel);

-- ─── 5. حملات مجدولة ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS broadcast_schedules (
    id              SERIAL      PRIMARY KEY,
    name            TEXT,
    segment_id      INT         REFERENCES audience_segments(id) ON DELETE SET NULL,
    channel         TEXT        NOT NULL CHECK (channel IN ('telegram','email')),
    message_payload JSONB       NOT NULL,                -- {text, image, subject, html, ...}
    schedule_type   TEXT        NOT NULL CHECK (schedule_type IN ('once','daily','weekly','custom_cron')),
    run_at          TIMESTAMPTZ,                          -- للـ once
    cron_expr       TEXT,                                 -- للـ custom_cron / daily/weekly تحويل لـ cron
    timezone        TEXT        DEFAULT 'Asia/Riyadh',
    enabled         BOOLEAN     DEFAULT TRUE,
    last_run_at     TIMESTAMPTZ,
    next_run_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      TEXT
);
CREATE INDEX IF NOT EXISTS idx_schedules_next ON broadcast_schedules (next_run_at)
    WHERE enabled = TRUE AND next_run_at IS NOT NULL;

-- ─── 6. ربط الـlogs بالشرائح + snapshot من القواعد ────────────────────────
ALTER TABLE broadcast_logs
    ADD COLUMN IF NOT EXISTS segment_id      INT REFERENCES audience_segments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rules_snapshot  JSONB,
    ADD COLUMN IF NOT EXISTS sent_count      INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS failed_count    INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS status          TEXT DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS schedule_id     INT REFERENCES broadcast_schedules(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS variant_a_text  TEXT,
    ADD COLUMN IF NOT EXISTS variant_b_text  TEXT;

ALTER TABLE email_logs
    ADD COLUMN IF NOT EXISTS segment_id      INT REFERENCES audience_segments(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rules_snapshot  JSONB,
    ADD COLUMN IF NOT EXISTS schedule_id     INT REFERENCES broadcast_schedules(id) ON DELETE SET NULL;

-- ─── 7. Indexes للأداء — الاستعلامات الثقيلة على action_logs ──────────────
-- مفيد لقواعد aggregate التي تعدّ تفاعلات حسب (user, action_type, store_id)
CREATE INDEX IF NOT EXISTS idx_al_audience_lookup
    ON action_logs (user_id, action_type, store_id, action_time DESC);

-- مفيد لقواعد event من سياق الترند
CREATE INDEX IF NOT EXISTS idx_al_trend_context
    ON action_logs (details, action_type)
    WHERE details LIKE 'trend:%';

-- مفيد لـ user_favorites lookup
CREATE INDEX IF NOT EXISTS idx_uf_tg_lookup
    ON user_favorites (telegram_id, kind, store_id, category_name);
CREATE INDEX IF NOT EXISTS idx_uf_web_lookup
    ON user_favorites (web_user_id, kind, store_id, category_name);

-- مفيد لـ story_views lookup
CREATE INDEX IF NOT EXISTS idx_sv_tg_lookup
    ON story_views (tg_user_id, was_trending, viewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_sv_web_lookup
    ON story_views (web_user_id, was_trending, viewed_at DESC);

COMMIT;

-- ─── ✅ تحقّق ─────────────────────────────────────────────────────────────
-- SELECT table_name FROM information_schema.tables
--  WHERE table_name IN ('audience_segments','audience_segment_versions',
--                       'broadcast_recipients','broadcast_exclusions','broadcast_schedules');
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name='broadcast_logs' AND column_name IN ('segment_id','rules_snapshot');
