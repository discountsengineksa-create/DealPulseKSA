-- ════════════════════════════════════════════════════════════════════════════
-- Migration 005: Bilingual support (English equivalents for master fields)
-- ════════════════════════════════════════════════════════════════════════════
-- يضيف 3 أعمدة لتخزين النسخة الإنجليزيّة لكل من:
--   * store_bio    → store_bio_en
--   * extra_offer  → extra_offer_en
--   * store_tags   → store_tags_en
--
-- name_en موجود مسبقاً (لا يُلمَس).
-- store_tags_en يتبع نفس نمط store_tags: نوع text + قيمة على شكل '{tag1,tag2}'.
-- التطبيق idempotent — آمن مع IF NOT EXISTS.
-- ════════════════════════════════════════════════════════════════════════════

ALTER TABLE master
    ADD COLUMN IF NOT EXISTS store_bio_en   TEXT,
    ADD COLUMN IF NOT EXISTS extra_offer_en TEXT,
    ADD COLUMN IF NOT EXISTS store_tags_en  TEXT;

-- index trgm على store_tags_en مماثل لـ idx_master_tags_trgm الموجود
CREATE INDEX IF NOT EXISTS idx_master_tags_en_trgm
    ON master USING gin (store_tags_en public.gin_trgm_ops);

-- index trgm على store_bio_en للبحث النصي السريع
CREATE INDEX IF NOT EXISTS idx_master_bio_en_trgm
    ON master USING gin (store_bio_en public.gin_trgm_ops);

-- ─── ✅ Done ─────────────────────────────────────────────────────────────────
-- بعد التطبيق:
--   master.store_bio_en   : TEXT (NULL مسموح للسجلات القديمة → COALESCE fallback للعربي)
--   master.extra_offer_en : TEXT (نفس الفكرة)
--   master.store_tags_en  : TEXT (مع GIN trgm index للبحث ILIKE %en_tag%)
