-- ============================================================================
-- 04_bronze_traffic.sql
-- Raw traffic submissions from operators.
-- Voice minutes, SMS counts, mobile data consumption, broken down by direction.
-- ============================================================================

CREATE TABLE bronze.traffic (
    bronze_id                       UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id            TEXT,
    operator_id                     VARCHAR(10),
    report_period                   VARCHAR(7),
    region_code                     VARCHAR(8),

    voice_minutes_onnet             BIGINT,
    voice_minutes_offnet_national   BIGINT,
    voice_minutes_international     BIGINT,

    sms_count_onnet                 BIGINT,
    sms_count_offnet_national       BIGINT,
    sms_count_international         BIGINT,

    data_consumed_gb_4g             NUMERIC(14, 3),
    data_consumed_gb_3g             NUMERIC(14, 3),
    data_consumed_gb_2g             NUMERIC(14, 3),

    submitted_at                    TIMESTAMPTZ,

    _source_file                    TEXT            NOT NULL,
    _source_line                    INTEGER         NOT NULL,
    _loaded_at                      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id               UUID            NOT NULL,
    _raw_payload                    JSONB           NOT NULL
);

CREATE INDEX idx_bronze_traffic_operator_period
    ON bronze.traffic (operator_id, report_period);

CREATE INDEX idx_bronze_traffic_loaded_at
    ON bronze.traffic (_loaded_at);

CREATE INDEX idx_bronze_traffic_source_file
    ON bronze.traffic (_source_file);

CREATE INDEX idx_bronze_traffic_run
    ON bronze.traffic (_loaded_by_run_id);

COMMENT ON TABLE bronze.traffic IS 'Raw traffic submissions: voice, SMS, data consumption by region and operator.';
COMMENT ON COLUMN bronze.traffic.data_consumed_gb_4g IS 'Mobile data consumed on 4G in GB. Numeric to handle fractional GB precisely.';
COMMENT ON COLUMN bronze.traffic.data_consumed_gb_3g IS 'Mobile data consumed on 3G in GB.';
COMMENT ON COLUMN bronze.traffic.data_consumed_gb_2g IS 'Mobile data consumed on 2G in GB. Declining as 2G is decommissioned.';