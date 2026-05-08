-- ============================================================================
-- 007_silver_traffic_internet.sql
-- Silver layer for internet/data traffic across mobile and fixed broadband.
--
-- Mobile rows use the 2G/3G/4G/5G generation column family.
-- Fixed broadband rows use the fiber/ADSL/fixed-wireless access column family.
-- Non-applicable columns may be NULL or zero because the bronze generators
-- currently write zero for fields outside the active service segment.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.traffic_internet (
    silver_id                           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                           UUID            NOT NULL UNIQUE,

    -- Business keys.
    operator_id                         VARCHAR(10)     NOT NULL,
    report_period                       VARCHAR(7)      NOT NULL,
    region_code                         VARCHAR(8)      NOT NULL,
    service_segment                     VARCHAR(30)     NOT NULL,

    -- Mobile data by network generation. NULL or zero for fixed broadband rows.
    data_consumed_mb_2g                 NUMERIC(18, 3)  CHECK (data_consumed_mb_2g IS NULL OR data_consumed_mb_2g >= 0),
    data_consumed_mb_3g                 NUMERIC(18, 3)  CHECK (data_consumed_mb_3g IS NULL OR data_consumed_mb_3g >= 0),
    data_consumed_mb_4g                 NUMERIC(18, 3)  CHECK (data_consumed_mb_4g IS NULL OR data_consumed_mb_4g >= 0),
    data_consumed_mb_5g                 NUMERIC(18, 3)  CHECK (data_consumed_mb_5g IS NULL OR data_consumed_mb_5g >= 0),

    -- Fixed broadband data by access technology. NULL or zero for mobile rows.
    data_consumed_mb_fiber              NUMERIC(18, 3)  CHECK (data_consumed_mb_fiber IS NULL OR data_consumed_mb_fiber >= 0),
    data_consumed_mb_adsl               NUMERIC(18, 3)  CHECK (data_consumed_mb_adsl IS NULL OR data_consumed_mb_adsl >= 0),
    data_consumed_mb_fixed_wireless     NUMERIC(18, 3)  CHECK (data_consumed_mb_fixed_wireless IS NULL OR data_consumed_mb_fixed_wireless >= 0),

    -- Derived metrics.
    period_start_date                   DATE            NOT NULL,
    total_data_consumed_mb              NUMERIC(18, 3)  NOT NULL CHECK (total_data_consumed_mb >= 0),

    -- Lineage.
    submitted_at                        TIMESTAMPTZ     NOT NULL,
    bronze_loaded_at                    TIMESTAMPTZ     NOT NULL,
    validated_by_run_id                 UUID,
    silver_loaded_at                    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_silver_traffic_internet_business_key
        UNIQUE (operator_id, report_period, region_code, service_segment),

    CONSTRAINT fk_silver_traffic_internet_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.traffic_internet (bronze_id),

    CONSTRAINT fk_silver_traffic_internet_run
        FOREIGN KEY (validated_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_internet_segment_period
    ON silver.traffic_internet (service_segment, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_internet_operator_period
    ON silver.traffic_internet (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_internet_region_period
    ON silver.traffic_internet (region_code, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_internet_run
    ON silver.traffic_internet (validated_by_run_id);

COMMENT ON TABLE silver.traffic_internet IS
'Validated internet traffic. Mobile rows populate generation columns; fixed broadband rows populate access-technology columns. Derived total_data_consumed_mb normalizes both segment shapes for analytics.';

CREATE TABLE IF NOT EXISTS silver.traffic_internet_rejections (
    rejection_id                        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                           UUID            NOT NULL UNIQUE,
    rejection_reason                    TEXT            NOT NULL,
    rejection_codes                     TEXT[]          NOT NULL,
    rejected_at                         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rejected_by_run_id                  UUID,

    CONSTRAINT fk_traffic_internet_rejections_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.traffic_internet (bronze_id),

    CONSTRAINT fk_traffic_internet_rejections_run
        FOREIGN KEY (rejected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_traffic_internet_rejections_codes
    ON silver.traffic_internet_rejections USING GIN (rejection_codes);

CREATE INDEX IF NOT EXISTS idx_traffic_internet_rejections_run
    ON silver.traffic_internet_rejections (rejected_by_run_id);

COMMENT ON TABLE silver.traffic_internet_rejections IS
'Bronze internet traffic rows that failed silver validation, with machine-readable reason codes.';
