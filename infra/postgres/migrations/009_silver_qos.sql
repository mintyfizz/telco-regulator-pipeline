-- ============================================================================
-- 009_silver_qos.sql
-- Silver layer for Quality of Service measurements.
--
-- QoS is segment-specific:
--   - mobile rows use radio/network quality columns
--   - fixed_voice rows use availability and repair-time columns
--   - fixed_broadband rows use fixed throughput, packet loss, latency,
--     coverage, and repair-time columns
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.qos (
    silver_id                           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                           UUID            NOT NULL UNIQUE,

    -- Business keys.
    operator_id                         VARCHAR(10)     NOT NULL,
    report_period                       VARCHAR(7)      NOT NULL,
    region_code                         VARCHAR(8)      NOT NULL,
    service_segment                     VARCHAR(30)     NOT NULL,
    measurement_methodology             VARCHAR(40)     NOT NULL,
    period_type                         VARCHAR(20)     NOT NULL,

    -- Shared/mobile QoS columns.
    network_availability_pct            NUMERIC(6, 3)   CHECK (network_availability_pct IS NULL OR (network_availability_pct >= 0 AND network_availability_pct <= 100)),
    call_drop_rate_pct                  NUMERIC(6, 3)   CHECK (call_drop_rate_pct IS NULL OR (call_drop_rate_pct >= 0 AND call_drop_rate_pct <= 100)),
    call_setup_success_rate_pct         NUMERIC(6, 3)   CHECK (call_setup_success_rate_pct IS NULL OR (call_setup_success_rate_pct >= 0 AND call_setup_success_rate_pct <= 100)),
    avg_data_throughput_mbps_4g         NUMERIC(8, 3)   CHECK (avg_data_throughput_mbps_4g IS NULL OR avg_data_throughput_mbps_4g >= 0),
    avg_data_throughput_mbps_3g         NUMERIC(8, 3)   CHECK (avg_data_throughput_mbps_3g IS NULL OR avg_data_throughput_mbps_3g >= 0),
    avg_latency_ms                      INTEGER         CHECK (avg_latency_ms IS NULL OR (avg_latency_ms >= 0 AND avg_latency_ms <= 5000)),
    population_coverage_pct_4g          NUMERIC(6, 3)   CHECK (population_coverage_pct_4g IS NULL OR (population_coverage_pct_4g >= 0 AND population_coverage_pct_4g <= 100)),
    population_coverage_pct_3g          NUMERIC(6, 3)   CHECK (population_coverage_pct_3g IS NULL OR (population_coverage_pct_3g >= 0 AND population_coverage_pct_3g <= 100)),
    population_coverage_pct_2g          NUMERIC(6, 3)   CHECK (population_coverage_pct_2g IS NULL OR (population_coverage_pct_2g >= 0 AND population_coverage_pct_2g <= 100)),

    -- Customer-side signal.
    qos_related_complaints              INTEGER         NOT NULL CHECK (qos_related_complaints >= 0),

    -- Fixed service quality metrics.
    avg_fixed_download_mbps             NUMERIC(8, 3)   CHECK (avg_fixed_download_mbps IS NULL OR avg_fixed_download_mbps >= 0),
    avg_fixed_upload_mbps               NUMERIC(8, 3)   CHECK (avg_fixed_upload_mbps IS NULL OR avg_fixed_upload_mbps >= 0),
    avg_packet_loss_pct                 NUMERIC(6, 3)   CHECK (avg_packet_loss_pct IS NULL OR (avg_packet_loss_pct >= 0 AND avg_packet_loss_pct <= 100)),
    fixed_broadband_coverage_pct        NUMERIC(6, 3)   CHECK (fixed_broadband_coverage_pct IS NULL OR (fixed_broadband_coverage_pct >= 0 AND fixed_broadband_coverage_pct <= 100)),
    fixed_service_repair_time_hours     NUMERIC(8, 3)   CHECK (fixed_service_repair_time_hours IS NULL OR fixed_service_repair_time_hours >= 0),

    -- Lineage.
    period_start_date                   DATE            NOT NULL,
    submitted_at                        TIMESTAMPTZ     NOT NULL,
    bronze_loaded_at                    TIMESTAMPTZ     NOT NULL,
    validated_by_run_id                 UUID,
    silver_loaded_at                    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_silver_qos_business_key
        UNIQUE (operator_id, report_period, region_code, service_segment),

    CONSTRAINT fk_silver_qos_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.qos (bronze_id),

    CONSTRAINT fk_silver_qos_run
        FOREIGN KEY (validated_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_qos_segment_period
    ON silver.qos (service_segment, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_qos_operator_period
    ON silver.qos (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_qos_region_period
    ON silver.qos (region_code, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_qos_methodology
    ON silver.qos (measurement_methodology);

CREATE INDEX IF NOT EXISTS idx_silver_qos_run
    ON silver.qos (validated_by_run_id);

COMMENT ON TABLE silver.qos IS
'Validated Quality of Service measurements. Segment-specific validation separates mobile radio metrics, fixed voice repair/availability metrics, and fixed broadband throughput/latency metrics.';

CREATE TABLE IF NOT EXISTS silver.qos_rejections (
    rejection_id                        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                           UUID            NOT NULL UNIQUE,
    rejection_reason                    TEXT            NOT NULL,
    rejection_codes                     TEXT[]          NOT NULL,
    rejected_at                         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rejected_by_run_id                  UUID,

    CONSTRAINT fk_qos_rejections_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.qos (bronze_id),

    CONSTRAINT fk_qos_rejections_run
        FOREIGN KEY (rejected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_qos_rejections_codes
    ON silver.qos_rejections USING GIN (rejection_codes);

CREATE INDEX IF NOT EXISTS idx_qos_rejections_run
    ON silver.qos_rejections (rejected_by_run_id);

COMMENT ON TABLE silver.qos_rejections IS
'Bronze QoS rows that failed silver validation, with machine-readable reason codes.';
