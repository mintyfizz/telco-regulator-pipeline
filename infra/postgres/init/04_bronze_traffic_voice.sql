-- ============================================================================
-- 04_bronze_traffic_voice.sql
-- Raw voice traffic submissions from operators.
--
-- Voice traffic is reported with directionality and destination:
--   - Outgoing: on-net (within same operator), off-net (to other Congolese
--     operators), international
--   - Incoming: from other national operators, from international networks
--
-- The on-net/off-net distinction drives interconnection settlements.
-- International traffic is regulated separately and often taxed differently.
-- ============================================================================

CREATE TABLE bronze.traffic_voice (
    bronze_id                               UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id                    TEXT,
    operator_id                             VARCHAR(10),
    report_period                           VARCHAR(7),
    region_code                             VARCHAR(8),

    -- Outgoing voice (calls placed by this operator's subscribers).
    voice_minutes_outgoing_onnet            BIGINT,
    voice_minutes_outgoing_offnet           BIGINT,
    voice_minutes_outgoing_international    BIGINT,

    -- Incoming voice (calls received by this operator's subscribers).
    voice_minutes_incoming_national         BIGINT,
    voice_minutes_incoming_international    BIGINT,

    submitted_at                            TIMESTAMPTZ,

    _source_file                            TEXT            NOT NULL,
    _source_line                            INTEGER         NOT NULL,
    _loaded_at                              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id                       UUID            NOT NULL,
    _raw_payload                            JSONB           NOT NULL
);

CREATE INDEX idx_bronze_traffic_voice_operator_period
    ON bronze.traffic_voice (operator_id, report_period);

CREATE INDEX idx_bronze_traffic_voice_loaded_at
    ON bronze.traffic_voice (_loaded_at);

CREATE INDEX idx_bronze_traffic_voice_run
    ON bronze.traffic_voice (_loaded_by_run_id);

COMMENT ON TABLE bronze.traffic_voice IS
'Voice call minutes broken out by direction (outgoing/incoming) and destination (on-net/off-net/international/national).';

COMMENT ON COLUMN bronze.traffic_voice.voice_minutes_outgoing_onnet IS
'Calls placed within the same operator network. Largest category in Congo (86% of outgoing in 2024).';

COMMENT ON COLUMN bronze.traffic_voice.voice_minutes_incoming_international IS
'Calls received from outside Congo. Drives international termination revenue.';