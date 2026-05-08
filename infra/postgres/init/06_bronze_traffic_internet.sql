-- ============================================================================
-- 06_bronze_traffic_internet.sql
-- Raw internet data consumption submissions from operators.
--
-- Internet traffic doesn't have on-net/off-net concept. Mobile data is broken
-- out by network generation. Fixed broadband is broken out by access technology.
--
-- Unit is megabytes (MB) to match ARPCE reporting convention. 1 GB = 1024 MB.
-- 4G dominates: 75% of Congo's mobile internet traffic in 2024 (and growing).
-- 2G is being phased out: only 0.3% of traffic in 2024.
-- ============================================================================

CREATE TABLE bronze.traffic_internet (
    bronze_id                       UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id            TEXT,
    operator_id                     VARCHAR(10),
    report_period                   VARCHAR(7),
    region_code                     VARCHAR(8),
    service_segment                 VARCHAR(30)     NOT NULL DEFAULT 'mobile',

    -- Mobile data consumed by technology generation, in megabytes.
    data_consumed_mb_2g             NUMERIC(18, 3),
    data_consumed_mb_3g             NUMERIC(18, 3),
    data_consumed_mb_4g             NUMERIC(18, 3),
    data_consumed_mb_5g             NUMERIC(18, 3),

    -- Fixed broadband data consumed by access technology, in megabytes.
    data_consumed_mb_fiber          NUMERIC(18, 3),
    data_consumed_mb_adsl           NUMERIC(18, 3),
    data_consumed_mb_fixed_wireless NUMERIC(18, 3),

    submitted_at                    TIMESTAMPTZ,

    _source_file                    TEXT            NOT NULL,
    _source_line                    INTEGER         NOT NULL,
    _loaded_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id               UUID            NOT NULL,
    _raw_payload                    JSONB           NOT NULL,

    CONSTRAINT fk_bronze_traffic_internet_run
        FOREIGN KEY (_loaded_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX idx_bronze_traffic_internet_segment_operator_period_region
    ON bronze.traffic_internet (service_segment, operator_id, report_period, region_code);

CREATE INDEX idx_bronze_traffic_internet_segment
    ON bronze.traffic_internet (service_segment);

CREATE INDEX idx_bronze_traffic_internet_loaded_at
    ON bronze.traffic_internet (_loaded_at);

CREATE INDEX idx_bronze_traffic_internet_run
    ON bronze.traffic_internet (_loaded_by_run_id);

COMMENT ON TABLE bronze.traffic_internet IS
'Internet data consumption in megabytes. Mobile rows use 2G/3G/4G/5G columns; fixed_broadband rows use fiber/ADSL/fixed-wireless columns.';

COMMENT ON COLUMN bronze.traffic_internet.service_segment IS
'Top-level operator segment: mobile, fixed_voice, fixed_broadband, postal, satellite. Current generator populates mobile and fixed_broadband for internet traffic.';

COMMENT ON COLUMN bronze.traffic_internet.data_consumed_mb_4g IS
'Dominant traffic category in Congo as of 2024 (75% of total). Growing 39%+ annually.';

COMMENT ON COLUMN bronze.traffic_internet.data_consumed_mb_2g IS
'Legacy traffic, declining as operators decommission 2G infrastructure. <1% of total.';

COMMENT ON COLUMN bronze.traffic_internet.data_consumed_mb_fiber IS
'Fixed broadband traffic delivered over fiber. Populated for fixed_broadband segment rows.';
