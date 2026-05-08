-- ============================================================================
-- 04_bronze_traffic_voice.sql
-- Raw voice traffic submissions from operators.
--
-- Voice traffic is reported with directionality and destination:
--   - Mobile outgoing: on-net, off-net, international
--   - Mobile incoming: national, international
--   - Fixed voice: local, national, international outgoing/incoming
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
    service_segment                         VARCHAR(30)     NOT NULL DEFAULT 'mobile',

    -- Outgoing voice (calls placed by this operator's subscribers).
    voice_minutes_outgoing_onnet            BIGINT,
    voice_minutes_outgoing_offnet           BIGINT,
    voice_minutes_outgoing_international    BIGINT,

    -- Incoming voice (calls received by this operator's subscribers).
    voice_minutes_incoming_national         BIGINT,
    voice_minutes_incoming_international    BIGINT,

    -- Fixed voice traffic. NULL/0 for mobile rows.
    voice_minutes_fixed_local                   BIGINT,
    voice_minutes_fixed_national                BIGINT,
    voice_minutes_fixed_international_outgoing  BIGINT,
    voice_minutes_fixed_incoming_national       BIGINT,
    voice_minutes_fixed_incoming_international  BIGINT,

    submitted_at                            TIMESTAMPTZ,

    _source_file                            TEXT            NOT NULL,
    _source_line                            INTEGER         NOT NULL,
    _loaded_at                              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id                       UUID            NOT NULL,
    _raw_payload                            JSONB           NOT NULL,

    CONSTRAINT fk_bronze_traffic_voice_run
        FOREIGN KEY (_loaded_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX idx_bronze_traffic_voice_segment_operator_period_region
    ON bronze.traffic_voice (service_segment, operator_id, report_period, region_code);

CREATE INDEX idx_bronze_traffic_voice_segment
    ON bronze.traffic_voice (service_segment);

CREATE INDEX idx_bronze_traffic_voice_loaded_at
    ON bronze.traffic_voice (_loaded_at);

CREATE INDEX idx_bronze_traffic_voice_run
    ON bronze.traffic_voice (_loaded_by_run_id);

COMMENT ON TABLE bronze.traffic_voice IS
'Voice call minutes broken out by direction (outgoing/incoming) and destination (on-net/off-net/international/national).';

COMMENT ON COLUMN bronze.traffic_voice.service_segment IS
'Top-level operator segment: mobile, fixed_voice, fixed_broadband, postal, satellite. Current generator populates mobile and fixed_voice for voice traffic.';

COMMENT ON COLUMN bronze.traffic_voice.voice_minutes_outgoing_onnet IS
'Calls placed within the same operator network. Largest category in Congo (86% of outgoing in 2024).';

COMMENT ON COLUMN bronze.traffic_voice.voice_minutes_incoming_international IS
'Calls received from outside Congo. Drives international termination revenue.';

COMMENT ON COLUMN bronze.traffic_voice.voice_minutes_fixed_local IS
'Fixed-line local voice minutes. Populated for fixed_voice segment rows.';
