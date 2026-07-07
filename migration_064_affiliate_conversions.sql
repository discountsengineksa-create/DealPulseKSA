-- migration_064_affiliate_conversions.sql
-- Real revenue attribution — capture postback events from affiliate networks.
--
-- Why: platform currently tracks clicks/copies (proxy metrics) but has zero
-- visibility into ACTUAL SALES/COMMISSION. This blocks the enterprise-grade
-- mandate (analysis_rebuild_strategy) and leaves the owner blind on which
-- stores actually convert. Postback is the industry-standard way affiliate
-- networks (Admitad, Impact, Salla, ...) report attributed sales S2S.
--
-- Model:
--   • (network, action_id) is the natural key — Admitad sends multiple
--     postbacks as status transitions (pending → approved → declined). We
--     UPSERT on this key so the row always holds the CURRENT status.
--   • `subid` is what WE sent when injecting into the affiliate URL at
--     click time. Format: `{master_id}_{visitor_id_short}` — lets us
--     correlate a conversion back to the exact click on our side.
--   • `raw_query` (JSONB) preserves the full postback payload for audit.

CREATE TABLE IF NOT EXISTS affiliate_conversions (
    id              BIGSERIAL PRIMARY KEY,
    network         TEXT      NOT NULL DEFAULT 'admitad',
    action_id       TEXT      NOT NULL,
    master_id       INTEGER,
    subid           TEXT,
    order_id        TEXT,
    offer_id        TEXT,
    action_type     TEXT,
    status          TEXT,
    currency        TEXT,
    order_sum       NUMERIC(14,4),
    payment_sum     NUMERIC(14,4),
    reward_ready    NUMERIC(14,4),
    click_time      TIMESTAMPTZ,
    conversion_time TIMESTAMPTZ,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action_ip       TEXT,
    user_agent      TEXT,
    raw_query       JSONB
);

-- Natural key (per-network); Admitad's action_id is a string.
CREATE UNIQUE INDEX IF NOT EXISTS uq_affconv_network_action
    ON affiliate_conversions(network, action_id);

CREATE INDEX IF NOT EXISTS ix_affconv_master
    ON affiliate_conversions(master_id);
CREATE INDEX IF NOT EXISTS ix_affconv_status
    ON affiliate_conversions(status);
CREATE INDEX IF NOT EXISTS ix_affconv_conversion_at
    ON affiliate_conversions(conversion_time DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS ix_affconv_received_at
    ON affiliate_conversions(received_at DESC);
