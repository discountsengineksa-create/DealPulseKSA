-- ═════════════════════════════════════════════════════════════════════════════
-- migration_065_type_debt_expand.sql   (2026-07-07)
--
-- PHASE A of the 3-phase Expand → Migrate → Contract cycle for master's
-- long-standing type debt on `is_trending` and `priority_score`.
--
-- WHY NOW: bot freeze was lifted (2026-07-07). See Claude_Memory/bot_frozen_lock.md
-- and db_foundation_audit.md → "Type debt".
--
-- WHAT THIS DOES (SAFE, ADDITIVE — no drops, fully reversible):
--   1. Adds `is_trending_bool` BOOLEAN (default FALSE) alongside the text column.
--   2. Adds `priority_score_int` SMALLINT (default 0) alongside the text column.
--   3. Backfills both from the existing text values using well-defined mappings.
--   4. Adds a composite index to preserve the sort semantic (trend first, then priority DESC).
--
-- WHAT THIS DOES NOT DO:
--   - Does NOT drop is_trending / priority_score (text). The contract migration
--     (migration_066) will drop them AFTER 24h of verified dual-write stability.
--   - Does NOT change any code paths. Those are updated in the same commit and
--     shipped together — but this migration is a no-op for existing code because
--     the old text columns remain untouched.
--
-- ROLLBACK: `ALTER TABLE master DROP COLUMN is_trending_bool, DROP COLUMN priority_score_int;`
--          Data preserved in old text columns.
-- ═════════════════════════════════════════════════════════════════════════════

BEGIN;

-- 1) ADD new columns (idempotent — safe to re-run)
ALTER TABLE master
    ADD COLUMN IF NOT EXISTS is_trending_bool   BOOLEAN  NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS priority_score_int SMALLINT NOT NULL DEFAULT 0;

-- 2) BACKFILL is_trending_bool from the text column
--    Only the exact string 'ترند 🔥' means TRUE. Everything else (NULL, 'عادي',
--    stray values) means FALSE. This matches every existing comparison site.
UPDATE master
   SET is_trending_bool = (is_trending = 'ترند 🔥')
 WHERE is_trending_bool IS DISTINCT FROM (is_trending = 'ترند 🔥');

-- 3) BACKFILL priority_score_int from the text column with a semantic mapping.
--    Levels found live in dashboard.py:2374 → ["عادي","مهم","عاجل","عاجل جداً"].
--    NOTE: The old TEXT sort DESC was BROKEN — 'مهم' (م=U+0645) lexically
--    outranked 'عاجل جداً' (ع=U+0639), so urgent items ranked LOWER than
--    important ones. This migration fixes the silent bug: 'عاجل جداً' (10) > 'عاجل' (6) > 'مهم' (3) > 'عادي' (0).
UPDATE master
   SET priority_score_int = CASE trim(COALESCE(priority_score, 'عادي'))
                              WHEN 'عاجل جداً' THEN 10
                              WHEN 'عاجل'      THEN 6
                              WHEN 'مهم'       THEN 3
                              WHEN 'عادي'      THEN 0
                              ELSE                  0
                            END
 WHERE priority_score_int IS DISTINCT FROM CASE trim(COALESCE(priority_score, 'عادي'))
                              WHEN 'عاجل جداً' THEN 10
                              WHEN 'عاجل'      THEN 6
                              WHEN 'مهم'       THEN 3
                              WHEN 'عادي'      THEN 0
                              ELSE                  0
                            END;

-- 4) INDEX for the composite sort used by bot + dashboard + api coupons ORDER BY.
--    Matches: ORDER BY is_trending_bool DESC, priority_score_int DESC
CREATE INDEX IF NOT EXISTS idx_master_trend_priority
    ON master (is_trending_bool DESC, priority_score_int DESC);

-- 5) VERIFICATION QUERIES (log the state after apply — read these in Railway console)
--    Expected: bool_true_count matches text_trend_count; each priority tier is separated correctly.
SELECT
    (SELECT COUNT(*) FROM master)                                            AS total_rows,
    (SELECT COUNT(*) FROM master WHERE is_trending_bool)                     AS bool_true_count,
    (SELECT COUNT(*) FROM master WHERE is_trending = 'ترند 🔥')              AS text_trend_count,
    (SELECT COUNT(*) FROM master WHERE priority_score_int > 0)               AS int_priority_nonzero,
    (SELECT COUNT(*) FROM master WHERE priority_score IS NOT NULL
                                   AND trim(priority_score) NOT IN ('عادي','')) AS text_priority_nonzero;

-- Distribution check — should show all mapped levels present in the data.
SELECT priority_score AS old_text, priority_score_int AS new_int, COUNT(*) AS rows
  FROM master
 GROUP BY 1, 2
 ORDER BY 2 DESC;

COMMIT;
