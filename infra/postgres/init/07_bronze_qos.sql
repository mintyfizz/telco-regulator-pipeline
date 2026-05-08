-- ============================================================================
-- 07_bronze_qos.sql
-- Raw Quality of Service submissions.
--
-- QoS is the most adversarial domain — operators have incentives to underreport
-- problems. We capture the methodology of measurement so silver-layer trust
-- scoring can weight independent measurements higher than self-reported ones.
-- ============================================================================

CREATE TABLE bronze.qos (
    bronze_id                           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id                TEXT,
    operator_id                         VARCHAR(10),
    report_period                       VARCHAR(7),
    region_code                         VARCHAR(8),
    service_segment                     VARCHAR(30)     NOT NULL DEFAULT 'mobile',

    -- How this measurement was obtained.
    measurement_methodology             VARCHAR(40),
    period_type                         VARCHAR(20),

    -- Network availability and call quality.
    network_availability_pct            NUMERIC(6, 3),
    call_drop_rate_pct                  NUMERIC(6, 3),
    call_setup_success_rate_pct         NUMERIC(6, 3),

    -- Data performance by technology generation.
    avg_data_throughput_mbps_4g         NUMERIC(8, 3),
    avg_data_throughput_mbps_3g         NUMERIC(8, 3),
    avg_latency_ms                      INTEGER,

    -- Coverage as percentage of regional population.
    population_coverage_pct_4g          NUMERIC(6, 3),
    population_coverage_pct_3g          NUMERIC(6, 3),
    population_coverage_pct_2g          NUMERIC(6, 3),

    -- Customer-side signal.
    qos_related_complaints              INTEGER,

    -- Fixed service quality metrics. NULL where not applicable.
    avg_fixed_download_mbps             NUMERIC(8, 3),
    avg_fixed_upload_mbps               NUMERIC(8, 3),
    avg_packet_loss_pct                 NUMERIC(6, 3),
    fixed_broadband_coverage_pct        NUMERIC(6, 3),
    fixed_service_repair_time_hours     NUMERIC(8, 3),

    submitted_at                        TIMESTAMPTZ,

    _source_file                        TEXT            NOT NULL,
    _source_line                        INTEGER         NOT NULL,
    _loaded_at                          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id                   UUID            NOT NULL,
    _raw_payload                        JSONB           NOT NULL,

    CONSTRAINT fk_bronze_qos_run
        FOREIGN KEY (_loaded_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX idx_bronze_qos_segment_operator_period_region
    ON bronze.qos (service_segment, operator_id, report_period, region_code);

CREATE INDEX idx_bronze_qos_methodology
    ON bronze.qos (measurement_methodology);

CREATE INDEX idx_bronze_qos_segment
    ON bronze.qos (service_segment);

CREATE INDEX idx_bronze_qos_loaded_at
    ON bronze.qos (_loaded_at);

CREATE INDEX idx_bronze_qos_run
    ON bronze.qos (_loaded_by_run_id);

COMMENT ON TABLE bronze.qos IS
'Raw Quality of Service measurements. The most adversarial domain in regulator data.';

COMMENT ON COLUMN bronze.qos.service_segment IS
'Top-level operator segment: mobile, fixed_voice, fixed_broadband, postal, satellite. Current generator populates mobile, fixed_voice, and fixed_broadband QoS rows.';

COMMENT ON COLUMN bronze.qos.measurement_methodology IS
'How this measurement was obtained: operator_self_reported (lowest trust), regulator_audit, independent_drive_test (highest trust).';

COMMENT ON COLUMN bronze.qos.period_type IS
'Granularity of measurement: monthly, weekly, daily, realtime. Defaults to monthly.';

COMMENT ON COLUMN bronze.qos.avg_fixed_download_mbps IS
'Average fixed broadband download throughput. Populated for fixed_broadband segment rows.';
