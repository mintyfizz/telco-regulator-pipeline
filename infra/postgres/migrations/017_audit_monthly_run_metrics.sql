-- ============================================================================
-- 017_audit_monthly_run_metrics.sql
-- Persist and surface run-level monthly reporting metrics for operations.
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit.monthly_reporting_run_metrics (
    report_period              VARCHAR(7) PRIMARY KEY,
    validation_window_start    TIMESTAMPTZ,
    validation_started_at      TIMESTAMPTZ NOT NULL,
    rows_ingested              BIGINT NOT NULL DEFAULT 0 CHECK (rows_ingested >= 0),
    rows_processed             BIGINT NOT NULL DEFAULT 0 CHECK (rows_processed >= 0),
    rows_validated             BIGINT NOT NULL DEFAULT 0 CHECK (rows_validated >= 0),
    rows_rejected              BIGINT NOT NULL DEFAULT 0 CHECK (rows_rejected >= 0),
    events_captured            BIGINT NOT NULL DEFAULT 0 CHECK (events_captured >= 0),
    alerts_triggered           BIGINT NOT NULL DEFAULT 0 CHECK (alerts_triggered >= 0),
    bronze_rows_by_domain      JSONB NOT NULL DEFAULT '{}'::jsonb,
    rejections_by_domain       JSONB NOT NULL DEFAULT '{}'::jsonb,
    validation_results         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_monthly_reporting_run_metrics_started_at
    ON audit.monthly_reporting_run_metrics (validation_started_at DESC);

CREATE OR REPLACE VIEW audit.v_monthly_reporting_run_health AS
SELECT
    m.report_period,
    m.validation_started_at,
    m.validation_window_start,
    m.rows_ingested,
    m.rows_processed,
    m.rows_validated,
    m.rows_rejected,
    m.events_captured,
    m.alerts_triggered,
    CASE
        WHEN m.rows_rejected > 0 OR m.alerts_triggered > 0 THEN 'attention'
        WHEN m.events_captured > 0 THEN 'watch'
        ELSE 'healthy'
    END AS run_health,
    m.bronze_rows_by_domain,
    m.rejections_by_domain,
    m.validation_results,
    m.updated_at
FROM audit.monthly_reporting_run_metrics m;

COMMENT ON TABLE audit.monthly_reporting_run_metrics IS
'Per-period operational metrics emitted by monthly_reporting_pipeline for observability and triage.';

COMMENT ON VIEW audit.v_monthly_reporting_run_health IS
'Operational health lens over monthly run metrics with coarse healthy/watch/attention classification.';
