-- ============================================================================
-- 03_bronze_subscribers.sql
-- Raw subscriber submissions from operators.
-- Captures source data exactly as received, with audit metadata.
-- ============================================================================

CREATE TABLE bronze.subscribers (
    -- Primary key: our own UUID, generated on insert.
    bronze_id                   UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source-provided fields (captured as-is from operator submissions).
    source_submission_id        TEXT,
    operator_id                 VARCHAR(10),
    report_period               VARCHAR(7),
    region_code                 VARCHAR(8),
    service_type                VARCHAR(20),
    total_subscribers           BIGINT,
    active_subscribers_30d      BIGINT,
    new_activations             BIGINT,
    churn_count                 BIGINT,
    arpu_xaf                    NUMERIC(10, 2),
    submitted_at                TIMESTAMPTZ,

    -- Audit columns (prefix-underscored to distinguish from source data).
    _source_file                TEXT            NOT NULL,
    _source_line                INTEGER         NOT NULL,
    _loaded_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id           UUID            NOT NULL,
    _raw_payload                JSONB           NOT NULL
);

CREATE INDEX idx_bronze_subscribers_operator_period
    ON bronze.subscribers (operator_id, report_period);

CREATE INDEX idx_bronze_subscribers_loaded_at
    ON bronze.subscribers (_loaded_at);

CREATE INDEX idx_bronze_subscribers_source_file
    ON bronze.subscribers (_source_file);

CREATE INDEX idx_bronze_subscribers_run
    ON bronze.subscribers (_loaded_by_run_id);

COMMENT ON TABLE bronze.subscribers IS 'Raw subscriber data submissions from operators. No validation, no deduplication.';
COMMENT ON COLUMN bronze.subscribers.bronze_id IS 'Internal primary key. Independent of any operator-supplied ID.';
COMMENT ON COLUMN bronze.subscribers.source_submission_id IS 'Operator-supplied submission ID, captured for reference. Not unique across the table.';
COMMENT ON COLUMN bronze.subscribers._raw_payload IS 'Original record as JSONB. Preserves any source fields not explicitly mapped to columns.';