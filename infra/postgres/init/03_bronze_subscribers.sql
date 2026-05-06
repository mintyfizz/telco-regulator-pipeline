-- ============================================================================
-- 03_bronze_subscribers.sql
-- Raw subscriber submissions from operators.
--
-- Subscriber data is segmented along three orthogonal dimensions:
--   1. service_category — what kind of service (mobile telephony, mobile internet, fixed)
--   2. payment_type — prepaid or postpaid
--   3. technology_generation — for internet only (2G, 3G, 4G, 5G)
--
-- A single physical subscriber can appear in multiple rows. For example a
-- prepaid mobile customer who uses 4G data appears once as mobile_telephony
-- and again as mobile_internet/4G. This matches how operator billing systems
-- structure customer data.
-- ============================================================================

CREATE TABLE bronze.subscribers (
    bronze_id                   UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source-provided fields.
    source_submission_id        TEXT,
    operator_id                 VARCHAR(10),
    report_period               VARCHAR(7),
    region_code                 VARCHAR(8),

    -- Three-dimensional service segmentation.
    service_category            VARCHAR(30),
    payment_type                VARCHAR(20),
    technology_generation       VARCHAR(10),

    -- The actual measurements.
    total_subscribers           BIGINT,
    active_subscribers_30d      BIGINT,
    new_activations             BIGINT,
    churn_count                 BIGINT,
    arpu_xaf                    NUMERIC(10, 2),

    submitted_at                TIMESTAMPTZ,

    -- Audit columns.
    _source_file                TEXT            NOT NULL,
    _source_line                INTEGER         NOT NULL,
    _loaded_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id           UUID            NOT NULL,
    _raw_payload                JSONB           NOT NULL
);

CREATE INDEX idx_bronze_subscribers_operator_period
    ON bronze.subscribers (operator_id, report_period);

CREATE INDEX idx_bronze_subscribers_category
    ON bronze.subscribers (service_category, technology_generation);

CREATE INDEX idx_bronze_subscribers_loaded_at
    ON bronze.subscribers (_loaded_at);

CREATE INDEX idx_bronze_subscribers_run
    ON bronze.subscribers (_loaded_by_run_id);

COMMENT ON TABLE bronze.subscribers IS
'Raw subscriber data submissions from operators. Segmented by service_category, payment_type, and (for internet) technology_generation.';

COMMENT ON COLUMN bronze.subscribers.service_category IS
'Type of service: mobile_telephony, mobile_internet, fixed_voice, fixed_broadband.';

COMMENT ON COLUMN bronze.subscribers.payment_type IS
'Billing model: prepaid (98%+ of African mobile market) or postpaid.';

COMMENT ON COLUMN bronze.subscribers.technology_generation IS
'Network generation for internet subscribers: 2G, 3G, 4G, 5G. NULL for telephony rows.';