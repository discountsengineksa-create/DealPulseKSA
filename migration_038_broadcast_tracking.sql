-- ════════════════════════════════════════════════════════════════════════════
-- Migration 038: Open + Click tracking للحملات
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف بنية tracking كاملة لاحتساب Open rate و CTR على الحملات البريدية
-- والتليجرام:
--   • broadcast_recipients.tracking_token     ← token فريد لكل مستلم (UUID)
--   • broadcast_recipients.clicked_at         ← تاريخ أول نقرة
--   • broadcast_link_targets                  ← روابط الحملة (لإعادة التوجيه)
--   • broadcast_link_clicks                   ← سجل نقرات-تفصيلي
--
-- آلية العمل:
--   1. عند الإرسال: كل مستلم يحصل tracking_token. كل URL في الرسالة يُسجَّل
--      في broadcast_link_targets ويُستبدل بـ https://<base>/bt/c/{token}/{id}
--   2. صورة 1x1 شفافة تُحقن في البريد: https://<base>/bt/o/{token}.gif
--   3. عند الفتح/النقر: endpoint يحدّث الحالة في broadcast_recipients
--      ويُسجّل التفاصيل في broadcast_link_clicks.
--
-- التطبيق: python api/run_migration.py migration_038_broadcast_tracking.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

-- ─── 1. أعمدة جديدة على broadcast_recipients ──────────────────────────────
ALTER TABLE broadcast_recipients
    ADD COLUMN IF NOT EXISTS tracking_token TEXT,
    ADD COLUMN IF NOT EXISTS clicked_at     TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS open_count     INT DEFAULT 0,
    ADD COLUMN IF NOT EXISTS click_count    INT DEFAULT 0;

-- token فريد عالمياً (يُولَّد عند الإرسال). Index UNIQUE للبحث السريع
CREATE UNIQUE INDEX IF NOT EXISTS idx_recipients_token
    ON broadcast_recipients (tracking_token)
    WHERE tracking_token IS NOT NULL;

COMMENT ON COLUMN broadcast_recipients.tracking_token IS
    'UUID فريد لكل مستلم — يُستخدم في pixel و click URLs لربط الحدث بالمستلم.';
COMMENT ON COLUMN broadcast_recipients.open_count IS
    'عدد مرات فتح الإيميل (≥1 = مفتوح). تليجرام دائماً 0 (لا دعم).';
COMMENT ON COLUMN broadcast_recipients.click_count IS
    'عدد مرات نقر روابط الحملة من هذا المستلم.';

-- ─── 2. جدول الروابط المُسجَّلة لكل حملة ──────────────────────────────────
-- نسجّل كل URL أصلي مرة واحدة لكل حملة، لاستخدام معرّف مختصر في الـ tracking URL
CREATE TABLE IF NOT EXISTS broadcast_link_targets (
    id              SERIAL      PRIMARY KEY,
    broadcast_id    INT         NOT NULL,
    broadcast_kind  TEXT        NOT NULL CHECK (broadcast_kind IN ('telegram','email')),
    original_url    TEXT        NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (broadcast_id, broadcast_kind, original_url)
);
CREATE INDEX IF NOT EXISTS idx_link_targets_broadcast
    ON broadcast_link_targets (broadcast_id, broadcast_kind);

COMMENT ON TABLE broadcast_link_targets IS
    'كل URL أصلي في حملة يُسجَّل هنا مرة، ثم نُستبدل في الجسم بـ /bt/c/{token}/{id}.';

-- ─── 3. سجل النقرات التفصيلي ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS broadcast_link_clicks (
    id              BIGSERIAL   PRIMARY KEY,
    recipient_id    BIGINT      REFERENCES broadcast_recipients(id) ON DELETE CASCADE,
    link_target_id  INT         REFERENCES broadcast_link_targets(id) ON DELETE CASCADE,
    clicked_at      TIMESTAMPTZ DEFAULT NOW(),
    ip_hash         TEXT,
    user_agent      TEXT,
    referrer        TEXT
);
CREATE INDEX IF NOT EXISTS idx_link_clicks_recipient
    ON broadcast_link_clicks (recipient_id);
CREATE INDEX IF NOT EXISTS idx_link_clicks_target
    ON broadcast_link_clicks (link_target_id);
CREATE INDEX IF NOT EXISTS idx_link_clicks_time
    ON broadcast_link_clicks (clicked_at DESC);

-- ─── 4. سجل فتح البريد التفصيلي (لتتبّع opens متعدّدة) ──────────────────
CREATE TABLE IF NOT EXISTS broadcast_email_opens (
    id              BIGSERIAL   PRIMARY KEY,
    recipient_id    BIGINT      REFERENCES broadcast_recipients(id) ON DELETE CASCADE,
    opened_at       TIMESTAMPTZ DEFAULT NOW(),
    ip_hash         TEXT,
    user_agent      TEXT
);
CREATE INDEX IF NOT EXISTS idx_email_opens_recipient
    ON broadcast_email_opens (recipient_id);

COMMIT;

-- ─── ✅ تحقّق ──────────────────────────────────────────────────────────────
-- SELECT column_name FROM information_schema.columns
--  WHERE table_name='broadcast_recipients'
--    AND column_name IN ('tracking_token','clicked_at','open_count','click_count');
-- SELECT table_name FROM information_schema.tables
--  WHERE table_name IN ('broadcast_link_targets','broadcast_link_clicks','broadcast_email_opens');
