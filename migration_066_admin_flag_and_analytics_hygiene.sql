-- migration_066_admin_flag_and_analytics_hygiene.sql (2026-07-07)
--
-- Two-part analytics hygiene fix discovered via live audit of production data:
--
-- FINDING 1 (evidence): The owner (dealpulseksa@gmail.com, web_users.id=1) shows
-- up as the top repeat visitor (16 visits in 30 days) in "returning visitors" —
-- his own admin browsing skews retention metrics. There is no is_admin flag to
-- exclude him from analytics automatically.
--
-- FINDING 2 (evidence, deferred to code): api/utils/fraud_scoring.py subtracts
-- exactly 50 from a base of 100 for datacenter ASNs — landing at score=50, which
-- exactly matches the dashboard's ">= 50" pass threshold. Result: 245/247 Dallas
-- visits (Google Cloud / AWS Dallas) leak through the "real users" filter. The
-- fix is a code change (subtract 60 instead of 50), shipping in the same commit.
--
-- What this migration DOES (additive, reversible):
--   1. ADD is_admin BOOLEAN NOT NULL DEFAULT FALSE to web_users
--   2. Set is_admin=TRUE for the confirmed owner account (id=1, verified email)
--   3. Add a small index on (is_admin) for cheap exclusion joins
--
-- What this migration DOES NOT DO:
--   - Does NOT mutate historical web_visits.quality_score. Historical rows keep
--     their scores as recorded (analytical evidence integrity). Dashboards use
--     the NEW filter clause (quality_score >= 50 AND is_datacenter IS NOT TRUE)
--     to exclude datacenter traffic explicitly — no data mutation needed.
--   - Does NOT touch the type-debt contract (that is migration_067, deferred 24h).
--
-- ROLLBACK: ALTER TABLE web_users DROP COLUMN is_admin;

BEGIN;

-- 1) Column
ALTER TABLE web_users
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- 2) Mark the owner. Match by BOTH id and email (safer than one field alone).
UPDATE web_users
   SET is_admin = TRUE
 WHERE id = 1
   AND email = 'dealpulseksa@gmail.com';

-- 3) Cheap index for excluding admins in analytics joins
CREATE INDEX IF NOT EXISTS idx_web_users_is_admin
    ON web_users (is_admin)
 WHERE is_admin;

-- 4) Verification — should return one row with is_admin=TRUE for the owner
SELECT id, email, phone_number, display_name, is_admin
  FROM web_users
 WHERE is_admin;

COMMIT;
