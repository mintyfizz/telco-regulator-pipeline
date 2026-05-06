-- ============================================================================
-- 06_bronze_traffic_internet.sql
-- Raw mobile internet data consumption submissions from operators.
--
-- Internet traffic doesn't have on-net/off-net concept (data goes to the
-- internet, not to other operators). Instead it's broken out by technology
-- generation: 2G, 3G, 4G, 5G.
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

    -- Data consumed by technology generation, in megabytes.
    data_consumed_mb_2g             NUMERIC(18, 3),
    data_consumed_mb_3g             NUMERIC(18, 3),
    data_consumed_mb_4g             NUMERIC(18, 3),
    data_consumed_mb_5g             NUMERIC(18, 3),

    submitted_at                    TIMESTAMPTZ,

    _source_file                    TEXT            NOT NULL,
    _source_line                    INTEGER         NOT NULL,
    _loaded_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id               UUID            NOT NULL,
    _raw_payload                    JSONB           NOT NULL
);

CREATE INDEX idx_bronze_traffic_internet_operator_period
    ON bronze.traffic_internet (operator_id, report_period);

CREATE INDEX idx_bronze_traffic_internet_loaded_at
    ON bronze.traffic_internet (_loaded_at);

CREATE INDEX idx_bronze_traffic_internet_run
    ON bronze.traffic_internet (_loaded_by_run_id);

COMMENT ON TABLE bronze.traffic_internet IS
'Mobile data consumption in megabytes, broken out by network technology generation. 5G column is nullable for markets where 5G is not yet deployed.';

COMMENT ON COLUMN bronze.traffic_internet.data_consumed_mb_4g IS
'Dominant traffic category in Congo as of 2024 (75% of total). Growing 39%+ annually.';

COMMENT ON COLUMN bronze.traffic_internet.data_consumed_mb_2g IS
'Legacy traffic, declining as operators decommission 2G infrastructure. <1% of total.';