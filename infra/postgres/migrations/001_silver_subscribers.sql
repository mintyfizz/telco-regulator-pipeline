-- ============================================================================
-- 11_silver_subscribers.sql
-- Silver layer for subscriber data.
--
-- Bronze accepts structurally valid operator submissions. Silver applies
-- business rules and separates clean analytical rows from rejected rows.
--
-- Objects created here:
--   1. silver.subscribers - clean, validated rows ready for analytics
--   2. silver.subscribers_rejections - rejected bronze rows with reason codes
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.subscribers (
    silver_id                   UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                   UUID            NOT NULL UNIQUE,

    -- Business keys.
    operator_id                 VARCHAR(10)     NOT NULL,
    report_period               VARCHAR(7)      NOT NULL,
    region_code                 VARCHAR(8)      NOT NULL,
    service_segment             VARCHAR(30)     NOT NULL,
    service_category            VARCHAR(30)     NOT NULL,
    payment_type                VARCHAR(20)     NOT NULL,
    technology_generation       VARCHAR(10),

    -- Cleaned measurements.
    total_subscribers           BIGINT          NOT NULL CHECK (total_subscribers >= 0),
    active_subscribers_30d      BIGINT          NOT NULL CHECK (active_subscribers_30d >= 0),
    new_activations             BIGINT          NOT NULL CHECK (new_activations >= 0),
    churn_count                 BIGINT          NOT NULL CHECK (churn_count >= 0),
    arpu_xaf                    NUMERIC(10, 2)  NOT NULL CHECK (arpu_xaf >= 0),

    -- Lineage and timing.
    period_start_date           DATE            NOT NULL,
    submitted_at                TIMESTAMPTZ     NOT NULL,
    bronze_loaded_at            TIMESTAMPTZ     NOT NULL,
    validated_by_run_id         UUID,
    silver_loaded_at            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_silver_subscribers_business_key
        UNIQUE NULLS NOT DISTINCT (
            operator_id,
            report_period,
            region_code,
            service_segment,
            service_category,
            payment_type,
            technology_generation
        ),

    CONSTRAINT fk_silver_subscribers_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.subscribers (bronze_id),

    CONSTRAINT fk_silver_subscribers_run
        FOREIGN KEY (validated_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_subscribers_segment_period
    ON silver.subscribers (service_segment, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_subscribers_operator_period
    ON silver.subscribers (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_subscribers_region_period
    ON silver.subscribers (region_code, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_subscribers_run
    ON silver.subscribers (validated_by_run_id);

COMMENT ON TABLE silver.subscribers IS
'Validated subscriber data. Every row passed reference checks and subscriber-domain business rules.';

COMMENT ON COLUMN silver.subscribers.technology_generation IS
'Required for mobile_internet rows; NULL for mobile_telephony, fixed_voice, and fixed_broadband rows.';

CREATE TABLE IF NOT EXISTS silver.subscribers_rejections (
    rejection_id                UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                   UUID            NOT NULL UNIQUE,
    rejection_reason            TEXT            NOT NULL,
    rejection_codes             TEXT[]          NOT NULL,
    rejected_at                 TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rejected_by_run_id          UUID,

    CONSTRAINT fk_subscribers_rejections_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.subscribers (bronze_id),

    CONSTRAINT fk_subscribers_rejections_run
        FOREIGN KEY (rejected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_subscribers_rejections_codes
    ON silver.subscribers_rejections USING GIN (rejection_codes);

CREATE INDEX IF NOT EXISTS idx_subscribers_rejections_run
    ON silver.subscribers_rejections (rejected_by_run_id);

COMMENT ON TABLE silver.subscribers_rejections IS
'Bronze subscriber rows that failed silver validation. Each rejection keeps machine-readable reason codes.';
