-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 072 — الطلبات المؤكَّدة: من «وكيل» إلى إيراد حقيقي
--
-- لماذا: كل قياسنا حتى الآن يقف عند **نسخ الكود** — وهو وكيل صرّحنا بأنه وكيل
-- (المرجع: seo/ads_measurement_doctrine.md §16). الطلب المؤكَّد يقع **عند المتجر**
-- ويُسنَد **بالكود لا بالنقرة**، ويصل متأخّراً أياماً. هذا الجدول يستقبله فيصير:
--   • خطّ الأساس إيراداً لا نسخاً (§17)
--   • قيمة الكود لكل متجر محسوبة لا مخمّنة (§2-5) — شرط `tROAS`
--   • ومصدر ملف رفع OCI إلى Google Ads (§18)
--
-- 🔴 **الحارس الأهمّ: `UNIQUE (network, order_ref)`**
-- طلباتنا تُرفع يدوياً من لوحات الشبكات، وإعادة رفع ملف أو تداخل ملفّين **يضاعف
-- الإيراد** فتتعلّم المزايدة على ربح لم يقع (§19). رقم الطلب من الشبكة هو
-- `transaction_id` الذي يمنع ذلك — بلا استثناء.
--
-- ⚠️ لا مفتاح أجنبي على `master.store_id`: العمود **غير فريد** (مكرّر لمتجر واحد).
--
-- آمنة للإعادة (IF NOT EXISTS في كل عبارة).
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS affiliate_orders (
    id               BIGSERIAL PRIMARY KEY,
    network          TEXT        NOT NULL,   -- salla | admitad | boostiny | codemap | manual
    order_ref        TEXT        NOT NULL,   -- رقم الطلب في الشبكة = transaction_id
    store_id         TEXT,                   -- اسم المتجر عندنا (بلا FK — القيمة غير فريدة في master)
    order_date       DATE        NOT NULL,
    order_value_sar  NUMERIC,                -- قيمة السلة (إن توفّرت)
    commission_sar   NUMERIC     NOT NULL,   -- عمولتنا — الرقم الذي يهمّنا فعلاً
    currency         TEXT        NOT NULL DEFAULT 'SAR',
    status           TEXT        NOT NULL DEFAULT 'confirmed',  -- pending|confirmed|cancelled|refunded
    coupon_code      TEXT,                   -- الكود الذي أسند الطلب
    gclid            TEXT,                   -- مفتاح OCI إن جاء الزائر من إعلان
    client_id        TEXT,                   -- مفتاح Measurement Protocol إلى GA4
    campaign_id      BIGINT REFERENCES campaigns(id) ON DELETE SET NULL,
    uploaded_to_ads  BOOLEAN     NOT NULL DEFAULT FALSE,
    uploaded_at      TIMESTAMPTZ,
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- الحارس ضد العدّ المكرّر عند إعادة الرفع
    CONSTRAINT uq_affiliate_orders_ref UNIQUE (network, order_ref)
);

CREATE INDEX IF NOT EXISTS idx_orders_date    ON affiliate_orders (order_date DESC);
CREATE INDEX IF NOT EXISTS idx_orders_store   ON affiliate_orders (store_id);
CREATE INDEX IF NOT EXISTS idx_orders_status  ON affiliate_orders (status);

-- الطلبات القابلة للرفع إلى Google Ads: مؤكَّدة ولها مفتاح نقرة ولم تُرفع بعد
CREATE INDEX IF NOT EXISTS idx_orders_oci_pending
    ON affiliate_orders (order_date)
    WHERE gclid IS NOT NULL AND uploaded_to_ads = FALSE AND status = 'confirmed';
