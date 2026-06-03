-- ════════════════════════════════════════════════════════════════════════════
-- Migration 029: بلاغات الأكواد + تحليلات الستوري + سحب تلقائي للمتاجر
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف:
--   1. master.is_suspended / suspended_at / suspended_reason
--      → عَلَم سحب المتجر من واجهات العملاء (auto أو يدوي).
--   2. جدول code_reports  → بلاغ «الكود لا يعمل» من الموقع/الميني-ويب/البوت.
--      كل المبلّغين معروفون (مسجّلون) — لا بلاغات مجهولة.
--   3. جدول story_views   → فتح ستوري (مسجّلين فقط).
--   4. action_logs.story_view_id → يربط نسخة/زيارة من داخل الستوري بفتحته.
--
-- قاعدة السحب التلقائي: 10 مبلّغين فريدين خلال 60 دقيقة لنفس المتجر
--   → UPDATE master SET is_suspended = TRUE
--   → ops alert critical (إيميل + Telegram)
--   تطبيقها في api/routers/track.py بعد كل INSERT في code_reports.
--
-- صفر downtime — كلّ التغييرات additive + idempotent.
-- التطبيق:  python api/run_migration.py migration_029_reports_and_stories.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. أعمدة السحب على master ─────────────────────────────────────────────
ALTER TABLE master
    ADD COLUMN IF NOT EXISTS is_suspended     BOOLEAN     NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS suspended_at     TIMESTAMP,
    ADD COLUMN IF NOT EXISTS suspended_reason TEXT;

COMMENT ON COLUMN master.is_suspended IS
    'إذا TRUE، المتجر مسحوب من واجهات العملاء (الموقع/الميني-ويب/البوت). يُفعَّل تلقائياً بعد 10 بلاغات/ساعة.';
COMMENT ON COLUMN master.suspended_at IS
    'وقت السحب. NULL إذا is_suspended=FALSE.';
COMMENT ON COLUMN master.suspended_reason IS
    'سبب السحب: ''auto: 10 reports in 60min'' أو ''manual: <ملاحظة>''';

-- index لاستعلامات الإخفاء السريعة من /coupons
-- ملاحظة: لا نستخدم CURRENT_DATE داخل predicate (غير immutable في PG)؛
-- نكتفي بـ is_suspended وهو ما يحدّد الإخفاء عن العملاء.
CREATE INDEX IF NOT EXISTS idx_master_active_not_suspended
    ON master (id)
    WHERE NOT is_suspended;

-- ─── 2. جدول code_reports ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS code_reports (
    id                          BIGSERIAL PRIMARY KEY,
    -- ملاحظة: لا FK على master(store_id) لأن master.store_id غير فريد حالياً
    -- (يوجد تكرار قديم سيُعالَج في migration dedupe مستقلة).
    -- التطبيق يتحقّق من وجود المتجر قبل INSERT (api/utils/code_reports.py).
    store_id                    TEXT        NOT NULL,
    source                      TEXT        NOT NULL
                                CHECK (source IN ('web', 'telegram_miniapp', 'bot')),

    -- هوية المُبلّغ — يعتمد على المصدر:
    --   web              → web_user_id ملزم، tg_user_id NULL
    --   telegram_miniapp → tg_user_id ملزم، web_user_id NULL (قد يكون مُتاحاً لو ربط حسابه)
    --   bot              → tg_user_id ملزم، web_user_id NULL
    web_user_id                 BIGINT      REFERENCES web_users(id)   ON DELETE SET NULL,
    tg_user_id                  BIGINT,     -- telegram_id (لا FK لأن bot_users يستخدم telegram_id كـ PK غير ملزم بـ FK نمطياً)

    -- snapshot للتواصل (في حال حُذف الحساب لاحقاً نحتفظ بالبيانات لـ audit)
    reporter_name               TEXT,
    reporter_email              TEXT,
    reporter_phone              TEXT,
    reporter_telegram_username  TEXT,

    reported_code               TEXT,       -- نسخة الكود وقت البلاغ
    issue_note                  TEXT,       -- ملاحظة اختيارية من الموقع/الميني-ويب

    status                      TEXT        NOT NULL DEFAULT 'new'
                                CHECK (status IN ('new', 'seen', 'fixed', 'rejected')),
    triggered_auto_suspend      BOOLEAN     NOT NULL DEFAULT FALSE,

    ip_hash                     BYTEA,
    user_agent_hash             BYTEA,

    created_at                  TIMESTAMP   NOT NULL DEFAULT NOW(),
    resolved_at                 TIMESTAMP,
    resolved_note               TEXT,

    -- ضمان وجود هوية للمُبلّغ
    CONSTRAINT code_reports_reporter_present CHECK (
        web_user_id IS NOT NULL OR tg_user_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_code_reports_store_time
    ON code_reports (store_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_code_reports_status
    ON code_reports (status, created_at DESC);

-- يسرّع نافذة السحب التلقائي (60 دقيقة) — تعد مبلّغين فريدين لمتجر معيّن
CREATE INDEX IF NOT EXISTS idx_code_reports_recent
    ON code_reports (store_id, created_at DESC)
    WHERE status IN ('new', 'seen');

COMMENT ON TABLE code_reports IS
    'بلاغات العملاء لأكواد لا تعمل. كل المبلّغين معروفون (لا بلاغات مجهولة).';

-- ─── 3. جدول story_views ───────────────────────────────────────────────────
-- مسجّلون فقط — لا نتتبّع الزوار.
CREATE TABLE IF NOT EXISTS story_views (
    id              BIGSERIAL   PRIMARY KEY,
    view_id         UUID        NOT NULL UNIQUE,   -- يُمرَّر إلى /track لربط النسخ/الزيارة
    -- لا FK على master(store_id) — راجع التعليق في جدول code_reports.
    store_id        TEXT        NOT NULL,
    source          TEXT        NOT NULL CHECK (source IN ('web', 'telegram_miniapp')),

    -- هوية المشاهد — أحد الاثنين فقط
    web_user_id     BIGINT      REFERENCES web_users(id) ON DELETE SET NULL,
    tg_user_id      BIGINT,                         -- telegram_id

    viewed_at       TIMESTAMP   NOT NULL DEFAULT NOW(),
    ip_hash         BYTEA,
    user_agent_hash BYTEA,

    CONSTRAINT story_views_viewer_present CHECK (
        web_user_id IS NOT NULL OR tg_user_id IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_story_views_store_time
    ON story_views (store_id, viewed_at DESC);

CREATE INDEX IF NOT EXISTS idx_story_views_web_user
    ON story_views (web_user_id, viewed_at DESC)
    WHERE web_user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_story_views_tg_user
    ON story_views (tg_user_id, viewed_at DESC)
    WHERE tg_user_id IS NOT NULL;

COMMENT ON TABLE story_views IS
    'سجل فتح الستوري (للمسجّلين). كل صف = فتحة واحدة. مشاهدات متكرّرة = صفوف متعدّدة لنفس المستخدم.';

-- ─── 4. ربط الأحداث بالستوري (action_logs.story_view_id) ──────────────────
ALTER TABLE action_logs
    ADD COLUMN IF NOT EXISTS story_view_id UUID;

CREATE INDEX IF NOT EXISTS idx_action_logs_story_view
    ON action_logs (story_view_id, action_type)
    WHERE story_view_id IS NOT NULL;

COMMENT ON COLUMN action_logs.story_view_id IS
    'لو الحدث (نسخ/زيارة) نشأ من داخل ستوري، هذا UUID يربطه بـ story_views.view_id.';

COMMIT;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق سريع:
--   SELECT COUNT(*) FROM code_reports;       -- 0
--   SELECT COUNT(*) FROM story_views;        -- 0
--   SELECT column_name FROM information_schema.columns
--       WHERE table_name='master' AND column_name='is_suspended';
--   SELECT column_name FROM information_schema.columns
--       WHERE table_name='action_logs' AND column_name='story_view_id';
