-- ════════════════════════════════════════════════════════════════════════════
-- Migration 047: ثيمات الموقع (site_themes) — خلفيات المناسبات
-- ════════════════════════════════════════════════════════════════════════════
-- مكتبة ثيمات: كل ثيم = اسم + صورة خلفية (سطح مكتب + جوال اختياري). الأدمن
-- يفعّل واحداً من الداشبورد فتتغيّر خلفية الموقع والميني-ويب لكل الزوار.
--
-- «الثيم الأساسي» = لا ثيم مُفعَّل (كل الصفوف is_active=FALSE) → الخلفية الخضراء
-- الأصلية تعود (لا تُحذف أبداً، فهي افتراض الـ CSS). فهرس جزئي يضمن ثيماً
-- مُفعَّلاً واحداً كحدّ أقصى.
--
-- صفر downtime — additive + idempotent.
-- التطبيق:  python api/run_migration.py migration_047_site_themes.sql
-- ════════════════════════════════════════════════════════════════════════════

BEGIN;

CREATE TABLE IF NOT EXISTS site_themes (
    id                BIGSERIAL   PRIMARY KEY,
    name              TEXT        NOT NULL,
    desktop_url       TEXT        NOT NULL,   -- نهاري — سطح مكتب
    mobile_url        TEXT,                   -- نهاري — جوال (اختياري)
    desktop_dark_url  TEXT,                   -- ليلي — سطح مكتب (اختياري)
    mobile_dark_url   TEXT,                   -- ليلي — جوال (اختياري)
    is_active         BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- للجداول المُنشأة سابقاً بدون أعمدة الليلي:
ALTER TABLE site_themes ADD COLUMN IF NOT EXISTS desktop_dark_url TEXT;
ALTER TABLE site_themes ADD COLUMN IF NOT EXISTS mobile_dark_url  TEXT;

-- ثيم مُفعَّل واحد كحدّ أقصى (الافتراضي = لا شيء مُفعَّل = الخلفية الأصلية)
CREATE UNIQUE INDEX IF NOT EXISTS uq_site_themes_active
    ON site_themes (is_active) WHERE is_active;

COMMENT ON TABLE site_themes IS
    'ثيمات خلفية الموقع/الميني-ويب للمناسبات. is_active لواحد فقط؛ لا شيء مُفعَّل = الخلفية الأصلية.';

COMMIT;

-- ─── ✅ Done ──────────────────────────────────────────────────────────────
-- تحقّق: SELECT to_regclass('public.site_themes');
