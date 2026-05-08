-- ============================================================================
-- 003_silver_traffic_voice.sql
-- Silver layer for voice traffic data across mobile and fixed voice segments.
--
-- Mobile rows use the on-net/off-net/international column family.
-- Fixed voice rows use the local/national/international fixed column family.
-- Non-applicable columns may be NULL or zero because the bronze generators
-- currently write zero for fields outside the active service segment.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.traffic_voice (
    silver_id                                   UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                                   UUID            NOT NULL UNIQUE,

    -- Business keys.
    operator_id                                 VARCHAR(10)     NOT NULL,
    report_period                               VARCHAR(7)      NOT NULL,
    region_code                                 VARCHAR(8)      NOT NULL,
    service_segment                             VARCHAR(30)     NOT NULL,

    -- Mobile voice columns. NULL or zero for fixed voice rows.
    voice_minutes_outgoing_onnet                BIGINT          CHECK (voice_minutes_outgoing_onnet IS NULL OR voice_minutes_outgoing_onnet >= 0),
    voice_minutes_outgoing_offnet               BIGINT          CHECK (voice_minutes_outgoing_offnet IS NULL OR voice_minutes_outgoing_offnet >= 0),
    voice_minutes_outgoing_international        BIGINT          CHECK (voice_minutes_outgoing_international IS NULL OR voice_minutes_outgoing_international >= 0),
    voice_minutes_incoming_national             BIGINT          CHECK (voice_minutes_incoming_national IS NULL OR voice_minutes_incoming_national >= 0),
    voice_minutes_incoming_international        BIGINT          CHECK (voice_minutes_incoming_international IS NULL OR voice_minutes_incoming_international >= 0),

    -- Fixed voice columns. NULL or zero for mobile rows.
    voice_minutes_fixed_local                   BIGINT          CHECK (voice_minutes_fixed_local IS NULL OR voice_minutes_fixed_local >= 0),
    voice_minutes_fixed_national                BIGINT          CHECK (voice_minutes_fixed_national IS NULL OR voice_minutes_fixed_national >= 0),
    voice_minutes_fixed_international_outgoing  BIGINT          CHECK (voice_minutes_fixed_international_outgoing IS NULL OR voice_minutes_fixed_international_outgoing >= 0),
    voice_minutes_fixed_incoming_national       BIGINT          CHECK (voice_minutes_fixed_incoming_national IS NULL OR voice_minutes_fixed_incoming_national >= 0),
    voice_minutes_fixed_incoming_international  BIGINT          CHECK (voice_minutes_fixed_incoming_international IS NULL OR voice_minutes_fixed_incoming_international >= 0),

    -- Derived metrics for cross-segment analytics.
    period_start_date                           DATE            NOT NULL,
    total_outgoing_minutes                      BIGINT          NOT NULL CHECK (total_outgoing_minutes >= 0),
    total_incoming_minutes                      BIGINT          NOT NULL CHECK (total_incoming_minutes >= 0),

    -- Lineage.
    submitted_at                                TIMESTAMPTZ     NOT NULL,
    bronze_loaded_at                            TIMESTAMPTZ     NOT NULL,
    validated_by_run_id                         UUID,
    silver_loaded_at                            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_silver_traffic_voice_business_key
        UNIQUE (operator_id, report_period, region_code, service_segment),

    CONSTRAINT fk_silver_traffic_voice_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.traffic_voice (bronze_id),

    CONSTRAINT fk_silver_traffic_voice_run
        FOREIGN KEY (validated_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_voice_segment_period
    ON silver.traffic_voice (service_segment, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_voice_operator_period
    ON silver.traffic_voice (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_voice_region_period
    ON silver.traffic_voice (region_code, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_traffic_voice_run
    ON silver.traffic_voice (validated_by_run_id);

COMMENT ON TABLE silver.traffic_voice IS
'Validated voice traffic. Mobile rows populate on-net/off-net columns; fixed voice rows populate local/national/international columns. Derived totals normalize both segment shapes for analytics.';

CREATE TABLE IF NOT EXISTS silver.traffic_voice_rejections (
    rejection_id                                UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                                   UUID            NOT NULL UNIQUE,
    rejection_reason                            TEXT            NOT NULL,
    rejection_codes                             TEXT[]          NOT NULL,
    rejected_at                                 TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rejected_by_run_id                          UUID,

    CONSTRAINT fk_traffic_voice_rejections_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.traffic_voice (bronze_id),

    CONSTRAINT fk_traffic_voice_rejections_run
        FOREIGN KEY (rejected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_traffic_voice_rejections_codes
    ON silver.traffic_voice_rejections USING GIN (rejection_codes);

CREATE INDEX IF NOT EXISTS idx_traffic_voice_rejections_run
    ON silver.traffic_voice_rejections (rejected_by_run_id);

COMMENT ON TABLE silver.traffic_voice_rejections IS
'Bronze voice traffic rows that failed silver validation, with machine-readable reason codes.';
