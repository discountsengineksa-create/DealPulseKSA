-- Migration 006: Store Logo Support
-- Run once: psql -U postgres -d discounts_engine -f migration_006_logo.sql

ALTER TABLE master ADD COLUMN IF NOT EXISTS logo_url TEXT;

COMMENT ON COLUMN master.logo_url IS 'Public URL for store logo (Cloudinary CDN or any HTTPS URL). Used by Telegram bot send_photo and dashboard preview.';
