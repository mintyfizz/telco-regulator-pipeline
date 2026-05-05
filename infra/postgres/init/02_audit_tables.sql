-- ============================================================================
-- 02_audit_tables.sql
-- Pipeline run tracking and ingestion audit infrastructure.
-- Bronze tables reference these via _loaded_by_run_id.
-- ============================================================================

CREATE TABLE audit.pipeline_runs (
    run_id              UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    dag_id              VARCHAR(100)    NOT NULL,
    task_id             VARCHAR(100)    NOT NULL,
    started_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at        TIMESTAMPTZ,
    status              VARCHAR(20)     NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running', 'success', 'failed', 'cancelled')),
    records_processed   BIGINT          DEFAULT 0,
    records_failed      BIGINT          DEFAULT 0,
    error_message       TEXT,
    metadata            JSONB           DEFAULT '{}'::jsonb
);

CREATE INDEX idx_pipeline_runs_dag_started
    ON audit.pipeline_runs (dag_id, started_at DESC);

CREATE INDEX idx_pipeline_runs_status
    ON audit.pipeline_runs (status)
    WHERE status IN ('running', 'failed');

COMMENT ON TABLE audit.pipeline_runs IS 'Tracks every Airflow task execution that touches the warehouse.';
COMMENT ON COLUMN audit.pipeline_runs.metadata IS 'Free-form JSON for run-specific context: file paths, parameter values, etc.';

CREATE TABLE audit.file_ingestions (
    ingestion_id        UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    run_id              UUID            NOT NULL REFERENCES audit.pipeline_runs(run_id),
    source_file         TEXT            NOT NULL,
    source_bucket       VARCHAR(100)    NOT NULL,
    file_size_bytes     BIGINT          NOT NULL,
    file_checksum_sha256 VARCHAR(64),
    operator_id         VARCHAR(10),
    data_domain         VARCHAR(30)     NOT NULL,
    report_period       VARCHAR(7),
    rows_total          BIGINT,
    rows_loaded         BIGINT,
    rows_quarantined    BIGINT,
    ingested_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    UNIQUE (source_bucket, source_file, run_id)
);

CREATE INDEX idx_file_ingestions_operator_domain_period
    ON audit.file_ingestions (operator_id, data_domain, report_period);

CREATE INDEX idx_file_ingestions_run
    ON audit.file_ingestions (run_id);

COMMENT ON TABLE audit.file_ingestions IS 'One row per file ingested into bronze. Enables replay and forensics.';
COMMENT ON COLUMN audit.file_ingestions.file_checksum_sha256 IS 'Hash of file contents for integrity verification and deduplication.'; 