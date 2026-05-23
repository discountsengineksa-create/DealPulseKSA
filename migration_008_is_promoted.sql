-- Migration 008: Paid Promotion / Featured Stores
-- Run once: psql -U postgres -d discounts_engine -f migration_008_is_promoted.sql

ALTER TABLE master
    ADD COLUMN IF NOT EXISTS is_promoted BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN master.is_promoted IS
    'إشهار / إعلان مدفوع — يظهر المتجر في قسم "المتاجر المختارة" بالموقع. يدار من الداشبورد.';

-- Partial index — only the promoted rows are indexed (cheap, fast lookup)
CREATE INDEX IF NOT EXISTS idx_master_is_promoted
    ON master (is_promoted)
    WHERE is_promoted = TRUE;
