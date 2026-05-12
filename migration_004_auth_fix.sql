-- ════════════════════════════════════════════════════════════════════════════
-- Migration 004: إصلاح جدول password_reset_tokens
-- ════════════════════════════════════════════════════════════════════════════
-- المشكلة: الجدول كان موجوداً مسبقاً بمخطط ناقص قبل migration_003،
-- فـ CREATE TABLE IF NOT EXISTS تخطّاه ولم يُضِف الأعمدة الجديدة.
-- النتيجة: forgot-password يفشل بـ 500 لأن `created_at` غير موجود.
--
-- الحل: نُسقط الجدول ونعيد إنشاءه بالمخطط الصحيح.
-- آمن لأن الميزة لم تنجح أبداً، فلا توجد بيانات حقيقية.
-- ════════════════════════════════════════════════════════════════════════════

DROP TABLE IF EXISTS password_reset_tokens;

CREATE TABLE password_reset_tokens (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL REFERENCES web_users(id) ON DELETE CASCADE,
    code_hash   TEXT NOT NULL,           -- الكود مشفّر (sha256)
    expires_at  TIMESTAMP NOT NULL,      -- 15 دقيقة عادةً
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW(),
    request_ip  INET                      -- لمنع الـ abuse
);

CREATE INDEX idx_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX idx_reset_tokens_expires ON password_reset_tokens(expires_at);

-- ─── ✅ بعد التطبيق ─────────────────────────────────────────────────────
-- forgot-password سيقدر يقرأ created_at ويُسجّل tokens جديدة
-- reset-password سيقدر يتحقق من الكود
-- التطبيق idempotent: لو شغّلتها مرتين، النتيجة نفسها
