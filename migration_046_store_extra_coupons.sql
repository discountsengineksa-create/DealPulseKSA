-- ════════════════════════════════════════════════════════════════════════════
-- Migration 046: أكواد إضافية لكل متجر (store_extra_coupons)
-- ════════════════════════════════════════════════════════════════════════════
-- المتجر واحد (اسم/رابط أفلييت/شعار/وصف/تاقات ثابتة في master) لكنه قد يعطي
-- عدّة أكواد بعروض مختلفة. كل صف هنا = كود إضافي مستقل بعرضه الخاص:
--   public_coupon · discount_value · extra_offer (+en) · my_coupon · تواريخ.
--
-- «نفس الحسابات» مضمونة بلا أي شيء إضافي: كل التتبّع (نسخ/نقر/بحث/مفضّلة)
-- مفتاحه store_id لا الكود — فنسخ أي كود تتجمّع في عدّادات المتجر والترند.
-- الكود الرئيسي يبقى في master؛ هذا الجدول للأكواد الإضافية فقط.
--
-- صفر downtime — additive + idempotent.
-- التطبيق:  python api/run_migration.py migration_046_store_extra_coupons.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS store_extra_coupons (
    id              BIGSERIAL   PRIMARY KEY,
    master_id       INTEGER     NOT NULL REFERENCES master(id) ON DELETE CASCADE,
    public_coupon   TEXT,
    discount_value  TEXT,
    extra_offer     TEXT,
    extra_offer_en  TEXT,
    my_coupon       TEXT,
    start_date      DATE,
    end_date        DATE,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    sort_order      INTEGER     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_store_extra_coupons_master
    ON store_extra_coupons (master_id, is_active, sort_order, id);

COMMENT ON TABLE store_extra_coupons IS
    'أكواد إضافية للمتجر — عدّة عروض/أكواد لنفس المتجر. الكود الرئيسي في master. '
    'التتبّع/الحسابات بـ store_id (تتجمّع للمتجر تلقائياً).';

COMMIT;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق: SELECT to_regclass('public.store_extra_coupons');
