-- migration_059: قائمة انتظار Reels — كل 6 متاجر = Reel واحد، تلقائياً.
--
-- last_reeled_at NULL  → المتجر في قائمة الانتظار
-- last_reeled_at NOW() → ظهر في Reel سابق
--
-- بعد كل بث ناجح، يفحص الـdispatcher القائمة. لو ≥6 منتظرين → ينتج Reel،
-- يضع NOW() لكل المتاجر الـ6 المختارة (SELECT … FOR UPDATE SKIP LOCKED
-- يضمن عدم استهلاك نفس المجموعة مرتين عند البث المتزامن).
--
-- backfill: المتاجر الموجودة قبل هذه الـmigration نضع NOW() حتى لا تطفر دفعة
-- ضخمة من Reels عند أوّل تشغيل بعد النشر (يبنّن الحساب). إذا أراد المالك
-- backfill يدوي للمتاجر القديمة في Reels لاحقاً، يضع NULL بنفسه.
ALTER TABLE master ADD COLUMN IF NOT EXISTS last_reeled_at timestamptz;

UPDATE master
SET last_reeled_at = NOW()
WHERE last_reeled_at IS NULL;

-- index على عمود الترشيح + الـreverse-chronological (LIFO: آخر المنضافين أولاً)
CREATE INDEX IF NOT EXISTS idx_master_last_reeled_at_null
    ON master (id DESC)
    WHERE last_reeled_at IS NULL;
