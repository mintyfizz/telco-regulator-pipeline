-- ============================================================================
-- 005_silver_traffic_sms.sql
-- Silver layer for SMS traffic.
--
-- SMS is currently modeled only for the mobile segment. Non-mobile rows are
-- preserved in bronze but rejected by silver validation until fixed/ISP SMS
-- products are explicitly supported.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.traffic_sms (
    silver_id                           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                           UUID            NOT NULL UNIQUE,

    -- Business keys.
    operator_id                         VARCHAR(10)     NOT NULL,
    report_period                       VARCHAR(7)      NOT NULL,
    region_code                         VARCHAR(8)      NOT NULL,
    service_segment                     VARCHAR(30)     NOT NULL,

    -- Mobile SMS measures.
    sms_count_outgoing_onnet            BIGINT          NOT NULL CHECK (sms_count_outgoing_onnet >= 0),
    sms_count_outgoing_offnet           BIGINT          NOT NULL CHECK (sms_count_outgoing_offnet >= 0),
    sms_count_outgoing_international    BIGINT          NOT NULL CHECK (sms_count_outgoing_international >= 0),
    sms_count_incoming_national         BIGINT          NOT NULL CHECK (sms_count_incoming_national >= 0),

    -- Derived metrics.
    period_start_date                   DATE            NOT NULL,
    total_outgoing_sms                  BIGINT          NOT NULL CHECK (total_outgoing_sms >= 0),

    -- Lineage.
    submitted_at                        TIMESTAMPTZ     NOT NULL,
    bronze_loaded_at                    TIMESTAMPTZ     NOT NULL,
    validated_by_run_id                 UUID,
    silver_loaded_at                    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_silver_traffic_sms_business_key
        UNIQUE (operator_id, report_period, region_code, service_segment),

    CONSTRAINT fk_silver_traffic_sms_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.traffic_sms (bronze_id),

    CONSTRAINT fk_silver_traffic_sms_run
        FOREIGN KEY (validated_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_sms_segment_period
    ON silver.traffic_sms (service_segment, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_sms_operator_period
    ON silver.traffic_sms (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_sms_region_period
    ON silver.traffic_sms (region_code, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_sms_run
    ON silver.traffic_sms (validated_by_run_id);

COMMENT ON TABLE silver.traffic_sms IS
'Validated SMS traffic for the mobile segment. Derived total_outgoing_sms aggregates on-net, off-net, and international outgoing SMS.';

CREATE TABLE IF NOT EXISTS silver.traffic_sms_rejections (
    rejection_id                        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                           UUID            NOT NULL UNIQUE,
    rejection_reason                    TEXT            NOT NULL,
    rejection_codes                     TEXT[]          NOT NULL,
    rejected_at                         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rejected_by_run_id                  UUID,

    CONSTRAINT fk_traffic_sms_rejections_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.traffic_sms (bronze_id),

    CONSTRAINT fk_traffic_sms_rejections_run
        FOREIGN KEY (rejected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_traffic_sms_rejections_codes
    ON silver.traffic_sms_rejections USING GIN (rejection_codes);

CREATE INDEX IF NOT EXISTS idx_traffic_sms_rejections_run
    ON silver.traffic_sms_rejections (rejected_by_run_id);

COMMENT ON TABLE silver.traffic_sms_rejections IS
'Bronze SMS rows that failed silver validation, with machine-readable reason codes.';
