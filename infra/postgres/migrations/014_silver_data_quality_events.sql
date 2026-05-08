-- ============================================================================
-- 014_silver_data_quality_events.sql
-- Data quality event registry for suspicious but structurally valid data.
--
-- Bronze keeps raw rows. Silver validation decides what is impossible and what
-- is merely suspicious. Impossible rows stay in per-domain rejection tables;
-- suspicious rows can remain in silver facts while also producing records here
-- for downstream alerting, review workflows, and dashboards.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.data_quality_events (
    event_id                UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_fingerprint       TEXT            NOT NULL UNIQUE,

    -- Classification.
    domain                  VARCHAR(40)     NOT NULL,
    severity                VARCHAR(20)     NOT NULL
                                        CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    event_code              VARCHAR(100)    NOT NULL,
    event_message           TEXT            NOT NULL,
    detection_rule          VARCHAR(120)    NOT NULL,

    -- Business context. Nullable because some file-level events may not have
    -- region or row-level lineage.
    operator_id             VARCHAR(10),
    service_segment         VARCHAR(30),
    report_period           VARCHAR(7),
    region_code             VARCHAR(8),

    -- Row-level lineage. These are intentionally generic because one event
    -- table covers all domains.
    source_table            VARCHAR(80),
    source_id               UUID,
    bronze_id               UUID,

    -- Metric context.
    metric_name             VARCHAR(100),
    observed_value          NUMERIC(22, 6),
    expected_min            NUMERIC(22, 6),
    expected_max            NUMERIC(22, 6),

    -- Lifecycle.
    status                  VARCHAR(20)     NOT NULL DEFAULT 'open'
                                        CHECK (status IN ('open', 'acknowledged', 'resolved', 'false_positive')),
    detected_at             TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    detected_by_run_id      UUID,
    resolved_at             TIMESTAMPTZ,
    resolution_note         TEXT,
    metadata                JSONB           NOT NULL DEFAULT '{}'::JSONB,

    CONSTRAINT fk_data_quality_events_run
        FOREIGN KEY (detected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_data_quality_events_domain_period
    ON silver.data_quality_events (domain, report_period);

CREATE INDEX IF NOT EXISTS idx_data_quality_events_severity_status
    ON silver.data_quality_events (severity, status, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_data_quality_events_operator_period
    ON silver.data_quality_events (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_data_quality_events_run
    ON silver.data_quality_events (detected_by_run_id);

CREATE INDEX IF NOT EXISTS idx_data_quality_events_metadata
    ON silver.data_quality_events USING GIN (metadata);

COMMENT ON TABLE silver.data_quality_events IS
'Suspicious but structurally valid data quality findings. Rejected rows remain in per-domain rejection tables; warning/error/critical events here are used for alerting and dashboard review workflows.';

COMMENT ON COLUMN silver.data_quality_events.event_fingerprint IS
'Stable unique key for idempotent event creation, usually built from domain, rule, source row ID, and metric name.';

COMMENT ON COLUMN silver.data_quality_events.status IS
'Review lifecycle for operational follow-up: open, acknowledged, resolved, or false_positive.';
