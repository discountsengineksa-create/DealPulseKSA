-- Migration 012: Affiliate Cloaking — cloaked_slug على master
-- Week 4: إخفاء رابط الأفلييت الحقيقي خلف رابط وسيط /go/{cloaked_slug}
-- Run once: psql "$DATABASE_URL" -f migration_012_affiliate_cloaking.sql
-- آمن لإعادة التشغيل (IF NOT EXISTS + backfill على الصفوف الفارغة فقط).

BEGIN;

-- ──────────────────────────────────────────────────────────────────────────
-- 1) عمود الـ slug المُعمّى
-- ──────────────────────────────────────────────────────────────────────────
ALTER TABLE master
    ADD COLUMN IF NOT EXISTS cloaked_slug VARCHAR(64);

COMMENT ON COLUMN master.cloaked_slug IS
    'Slug عشوائي يُستخدم في /go/{cloaked_slug} لإخفاء رابط الأفلييت الحقيقي (Week 4).';

-- ──────────────────────────────────────────────────────────────────────────
-- 2) Backfill — slug فريد لكل صف قديم (10 خانات hex من md5)
--    نفس التعبير يُستخدم عند إضافة متجر جديد من dashboard.py للاتساق.
-- ──────────────────────────────────────────────────────────────────────────
UPDATE master
SET cloaked_slug = substr(
        md5(random()::text || clock_timestamp()::text || id::text), 1, 10)
WHERE cloaked_slug IS NULL OR cloaked_slug = '';

-- ──────────────────────────────────────────────────────────────────────────
-- 3) فهرس فريد — يمنع التصادم ويُسرّع البحث بالـ slug في /go
-- ──────────────────────────────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS uniq_master_cloaked_slug
    ON master(cloaked_slug);

COMMIT;
