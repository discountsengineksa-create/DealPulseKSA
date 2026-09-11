-- ═══════════════════════════════════════════════════════════════════════════
-- Migration 070 — منظومة إدارة الحملات + مفتاحا الإسناد
--
-- تُنفِّذ ما استُخلص من شهادات القياس والإسناد (المرجع: seo/ads_measurement_doctrine.md):
--   §16  هدف واحد لكل مرحلة، وإلا لا حكم على الحملة.
--   §17  لا تقرير يُغلق بلا عمود «الفعل».
--   §18  gclid مفتاح OCI، و client_id مفتاح Measurement Protocol.
--   §20  الوكيل (copy_coupon) يُقرأ ولا يقود المزايدة — يُعلَن أنه وكيل.
--   §23  القنوات غير-جوجل لا تُنسب بلا UTM.
--
-- آمنة للإعادة (IF NOT EXISTS في كل عبارة).
-- ═══════════════════════════════════════════════════════════════════════════

-- 1) الحملات — عقد القياس الذي يُملأ قبل الإطلاق لا بعده
CREATE TABLE IF NOT EXISTS campaigns (
    id                   BIGSERIAL PRIMARY KEY,
    name                 TEXT        NOT NULL,
    channel              TEXT        NOT NULL,   -- google_search | snapchat | tiktok | instagram | telegram | email | organic
    stage                TEXT        NOT NULL,   -- awareness | consideration | purchase | loyalty
    kpi_event            TEXT        NOT NULL,   -- copy_coupon | click_link | view_store | order_confirmed
    kpi_target           NUMERIC     NOT NULL,
    is_proxy_kpi         BOOLEAN     NOT NULL DEFAULT FALSE,  -- §16: الوكيل يُعلَن صراحةً
    baseline_value       NUMERIC,                -- معدود من action_logs قبل الإطلاق
    baseline_window_days INTEGER,
    starts_on            DATE        NOT NULL,
    ends_on              DATE        NOT NULL,
    budget_sar           NUMERIC,
    stop_rule            TEXT        NOT NULL,   -- متى نوقف — يُكتب قبل الإنفاق
    landing_url          TEXT        NOT NULL,
    utm_source           TEXT,
    utm_medium           TEXT,
    utm_campaign         TEXT,
    keywords             TEXT,                   -- كلمة في كل سطر (للبحث المدفوع)
    preflight            JSONB,                  -- نتيجة فحوص ما قبل الإطلاق
    preflight_passed     BOOLEAN     NOT NULL DEFAULT FALSE,
    status               TEXT        NOT NULL DEFAULT 'draft',  -- draft|ready|running|stopped|done
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_status  ON campaigns (status);
CREATE INDEX IF NOT EXISTS idx_campaigns_window  ON campaigns (starts_on, ends_on);

-- 2) قراءات الحملة — كل قراءة تُغلق بفعل (§17: قياس بلا فعل = هدف خاطئ)
CREATE TABLE IF NOT EXISTS campaign_readings (
    id              BIGSERIAL PRIMARY KEY,
    campaign_id     BIGINT      NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    read_on         DATE        NOT NULL DEFAULT CURRENT_DATE,
    kpi_actual      NUMERIC,
    spend_sar       NUMERIC,
    gsc_clicks      INTEGER,
    gsc_impressions INTEGER,
    gsc_position    NUMERIC,
    notes           TEXT,
    action_taken    TEXT        NOT NULL,        -- إلزامي بحكم §17
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaign_readings_campaign ON campaign_readings (campaign_id, read_on DESC);

-- 3) مفتاحا الإسناد — الواجهة ترسلهما منذ web bd208e3، والـAPI كان يُسقطهما
ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS gclid     TEXT;
ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS client_id TEXT;

-- فهرس جزئي: النقرات الإعلانية أقلية من الأحداث، فلا يُثقَل الجدول
CREATE INDEX IF NOT EXISTS idx_action_logs_gclid
    ON action_logs (gclid) WHERE gclid IS NOT NULL;
