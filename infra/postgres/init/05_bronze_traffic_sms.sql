-- ============================================================================
-- 05_bronze_traffic_sms.sql
-- Raw SMS traffic submissions from operators.
--
-- SMS volumes follow the same on-net/off-net/international pattern as voice,
-- but at much smaller absolute scale and declining year-over-year as users
-- shift to OTT messaging (WhatsApp, Messenger).
--
-- In Congo: SMS dropped from 5.5 billion in 2023 to 4.6 billion in 2024 (-15.7%).
-- ============================================================================

CREATE TABLE bronze.traffic_sms (
    bronze_id                           UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id                TEXT,
    operator_id                         VARCHAR(10),
    report_period                       VARCHAR(7),
    region_code                         VARCHAR(8),

    -- Outgoing SMS.
    sms_count_outgoing_onnet            BIGINT,
    sms_count_outgoing_offnet           BIGINT,
    sms_count_outgoing_international    BIGINT,

    -- Incoming SMS (typically only national tracked; international incoming SMS rarely reported).
    sms_count_incoming_national         BIGINT,

    submitted_at                        TIMESTAMPTZ,

    _source_file                        TEXT            NOT NULL,
    _source_line                        INTEGER         NOT NULL,
    _loaded_at                          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id                   UUID            NOT NULL,
    _raw_payload                        JSONB           NOT NULL
);

CREATE INDEX idx_bronze_traffic_sms_operator_period
    ON bronze.traffic_sms (operator_id, report_period);

CREATE INDEX idx_bronze_traffic_sms_loaded_at
    ON bronze.traffic_sms (_loaded_at);

CREATE INDEX idx_bronze_traffic_sms_run
    ON bronze.traffic_sms (_loaded_by_run_id);

COMMENT ON TABLE bronze.traffic_sms IS
'SMS message counts by direction and destination. Globally declining domain as OTT messaging dominates.';