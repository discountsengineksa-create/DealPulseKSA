-- ════════════════════════════════════════════════════════════════════════════
-- Migration 060: نبض الزوّار — تتبّع زيارات الموقع على مستوى الجلسة (web_visits)
-- ════════════════════════════════════════════════════════════════════════════
-- المشكلة التي يحلّها: الموقع لم يكن يسجّل «الزيارات» إطلاقاً في القاعدة —
-- فقط الأحداث الصريحة (نسخ/نقر/بحث في action_logs) والمسجّلين (web_users).
-- من يتصفّح فقط ويطلع لا يظهر في أي تحليل بالداشبورد. هذا الجدول يسدّ الفجوة:
-- صف واحد لكل جلسة تصفّح (لا لكل صفحة) ليبقى خفيفاً على القاعدة.
--
-- المصدر: /track/visit يُطلقه الموقع مرة واحدة لكل جلسة (sessionStorage uuid).
-- الإثراء الجغرافي/الجودة من نفس مسار action_logs (Cloudflare Worker headers).
-- visit_id فريد → ON CONFLICT DO NOTHING يجعل الـ ping idempotent.
--
-- التطبيق:  python api/run_migration.py migration_060_web_visits.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS web_visits (
    id              BIGSERIAL PRIMARY KEY,
    visit_id        UUID NOT NULL UNIQUE,        -- معرّف الجلسة من العميل (dedupe)
    -- هوية: NULL = زائر غير مسجّل · رقم = web_users.id (المصدر دائماً web)
    user_id         INTEGER REFERENCES web_users(id) ON DELETE SET NULL,
    source          TEXT NOT NULL DEFAULT 'web',
    -- مصدر الزيارة المُصنَّف: search / social / direct / internal / <host>
    referrer_kind   TEXT,
    referrer_host   TEXT,                         -- الهوست الخام للإحالة (google.com ...)
    landing_path    TEXT,                         -- أول صفحة دخل عليها (/store/noon)
    -- إثراء جغرافي + جودة (نفس أعمدة action_logs — مصدرها Cloudflare Worker)
    ip_hash         BYTEA,
    user_agent_hash BYTEA,
    country_code    TEXT,
    region_code     TEXT,
    city            TEXT,
    device_class    TEXT,
    asn             INTEGER,
    is_datacenter   BOOLEAN DEFAULT FALSE,
    cf_bot_score    SMALLINT,
    quality_score   SMALLINT,                     -- 0..100 (الداشبورد يفلتر >= 50 كزوّار حقيقيين)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- استعلامات الداشبورد كلها زمنية (زوّار اليوم/7/30) → فهرس تنازلي على التاريخ.
CREATE INDEX IF NOT EXISTS idx_web_visits_created
    ON web_visits (created_at DESC);

-- ربط الزيارة بالمسجّل (كم زائر تحوّل لمستخدم) — جزئي لتجاهل الزوّار.
CREATE INDEX IF NOT EXISTS idx_web_visits_user
    ON web_visits (user_id) WHERE user_id IS NOT NULL;

COMMIT;
