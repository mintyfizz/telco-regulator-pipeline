-- ============================================================================
-- 05_bronze_qos.sql
-- Raw Quality of Service submissions from operators.
-- Network availability, call quality, data throughput, coverage metrics.
-- ============================================================================

CREATE TABLE bronze.qos (
    bronze_id                           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id                TEXT,
    operator_id                         VARCHAR(10),
    report_period                       VARCHAR(7),
    region_code                         VARCHAR(8),

    network_availability_pct            NUMERIC(6, 3),
    call_drop_rate_pct                  NUMERIC(6, 3),
    call_setup_success_rate_pct         NUMERIC(6, 3),

    avg_data_throughput_mbps_4g         NUMERIC(8, 3),
    avg_data_throughput_mbps_3g         NUMERIC(8, 3),
    avg_latency_ms                      INTEGER,

    population_coverage_pct_4g          NUMERIC(6, 3),
    population_coverage_pct_3g          NUMERIC(6, 3),
    population_coverage_pct_2g          NUMERIC(6, 3),

    complaints_received                 INTEGER,

    submitted_at                        TIMESTAMPTZ,

    _source_file                        TEXT            NOT NULL,
    _source_line                        INTEGER         NOT NULL,
    _loaded_at                          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id                   UUID            NOT NULL,
    _raw_payload                        JSONB           NOT NULL
);

CREATE INDEX idx_bronze_qos_operator_period
    ON bronze.qos (operator_id, report_period);

CREATE INDEX idx_bronze_qos_loaded_at
    ON bronze.qos (_loaded_at);

CREATE INDEX idx_bronze_qos_source_file
    ON bronze.qos (_source_file);

CREATE INDEX idx_bronze_qos_run
    ON bronze.qos (_loaded_by_run_id);

COMMENT ON TABLE bronze.qos IS 'Raw Quality of Service submissions. The most adversarial domain — operators have incentives to underreport problems.';
COMMENT ON COLUMN bronze.qos.network_availability_pct IS 'Percentage uptime for the period. License-mandated KPI, typically targeted 99.5%+.';
COMMENT ON COLUMN bronze.qos.call_drop_rate_pct IS 'Percentage of calls dropped before normal completion. Lower is better, license target typically <2%.';
COMMENT ON COLUMN bronze.qos.avg_data_throughput_mbps_4g IS 'Average download speed on 4G. NULL for regions without 4G coverage.';