-- ════════════════════════════════════════════════════════════════════════════
-- Migration 050: إعدادات الشفافية العامة للموقع (site_visual_settings)
-- ════════════════════════════════════════════════════════════════════════════
-- جدول مفرد (singleton) يحمل قيم الشفافية و blur للكروت والأيقونات والستارة
-- فوق الثيم. الداشبورد يديره عبر «تحكم الشفافية» في صفحة الثيمات.
-- الموقع يستهلكه من /coupons/site-theme ويطبّقه كمتغيّرات CSS على <html>.
--
-- القيم الافتراضية تطابق ما هو موجود حالياً في globals.css بعد إعادة الضبط.
--
-- صفر downtime — additive + idempotent.
-- التطبيق:  python api/run_migration.py migration_050_site_visual_settings.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS site_visual_settings (
    id              INT          PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    overlay_opacity NUMERIC(4,3) NOT NULL DEFAULT 0.350,  -- ستارة فوق الثيم (0=الثيم كامل، 1=مخفي)
    card_opacity    NUMERIC(4,3) NOT NULL DEFAULT 0.420,  -- خلفية الكروت (.glass)
    icon_opacity    NUMERIC(4,3) NOT NULL DEFAULT 0.550,  -- خلفية أيقونات المتاجر
    blur_px         INT          NOT NULL DEFAULT 28      -- شدّة backdrop-blur للكروت
                                          CHECK (blur_px BETWEEN 0 AND 60),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- صف وحيد (singleton) — يُنشأ تلقائياً
INSERT INTO site_visual_settings (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE site_visual_settings IS
    'إعدادات الشفافية والـ blur العامة للموقع — تُطبَّق عند تفعيل أي ثيم. صف واحد فقط.';

COMMIT;

-- ─── ✅ تحقّق ─────────────────────────────────────────────────────────────
-- SELECT * FROM site_visual_settings;
