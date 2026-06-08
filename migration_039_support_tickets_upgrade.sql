-- ════════════════════════════════════════════════════════════════════════════
-- Migration 039: ترقية support_tickets لنظام دعم موحّد (بوت + ميني + موقع)
-- ════════════════════════════════════════════════════════════════════════════
-- لماذا: «مركز الدعم» في الداشبورد كان يقرأ support_tickets لكن لا شيء يملأه،
--        والرد لم يكن يُسلَّم للمستخدم. هذه الترقية تجعل الجدول يستقبل من
--        المنصّات الثلاث ويحمل هوية كافية ليرد الأدمن ويُسلَّم الرد عبر تلجرام.
--
-- يضيف (كلها additive + idempotent — صفر downtime):
--   source        : 'bot' | 'telegram_miniapp' | 'web'  (من أين جاء البلاغ)
--   web_user_id   : ربط بمستخدم الموقع (إن وُجد)
--   contact_name  : اسم المُرسِل (snapshot — للموقع أساساً)
--   contact_email : إيميله (للرد/التدقيق على عملياته)
--   contact_phone : جواله
--   reply_text    : رد الأدمن (يُحفظ للسجل)
--   replied_at    : وقت الرد
--   delivered     : هل وصل الرد للمستخدم فعلاً (عبر تلجرام)؟
--
-- التطبيق:  python api/run_migration.py migration_039_support_tickets_upgrade.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE support_tickets
    ADD COLUMN IF NOT EXISTS source        TEXT,
    ADD COLUMN IF NOT EXISTS web_user_id   BIGINT,
    ADD COLUMN IF NOT EXISTS contact_name  TEXT,
    ADD COLUMN IF NOT EXISTS contact_email TEXT,
    ADD COLUMN IF NOT EXISTS contact_phone TEXT,
    ADD COLUMN IF NOT EXISTS reply_text    TEXT,
    ADD COLUMN IF NOT EXISTS replied_at    TIMESTAMP,
    ADD COLUMN IF NOT EXISTS delivered     BOOLEAN NOT NULL DEFAULT FALSE;

-- القيم القديمة (إن وُجدت) نعتبرها من البوت
UPDATE support_tickets SET source = 'bot' WHERE source IS NULL;

COMMENT ON COLUMN support_tickets.source        IS 'منصّة البلاغ: bot | telegram_miniapp | web';
COMMENT ON COLUMN support_tickets.web_user_id   IS 'ربط بـ web_users.id إن جاء من الموقع.';
COMMENT ON COLUMN support_tickets.contact_email IS 'إيميل المُرسِل (snapshot) — للرد والتدقيق على عملياته.';
COMMENT ON COLUMN support_tickets.reply_text    IS 'رد الأدمن المحفوظ.';
COMMENT ON COLUMN support_tickets.delivered     IS 'TRUE إذا وصل الرد للمستخدم عبر تلجرام.';

-- فهرس لتسريع صندوق الوارد (المفتوحة أولاً، الأحدث أولاً)
CREATE INDEX IF NOT EXISTS idx_support_tickets_status_created
    ON support_tickets (status, created_at DESC);

COMMIT;
