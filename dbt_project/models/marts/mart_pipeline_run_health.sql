SELECT
  report_period,
  validation_started_at,
  validation_window_start,
  rows_ingested,
  rows_processed,
  rows_validated,
  rows_rejected,
  events_captured,
  alerts_triggered,
  run_health
FROM {{ ref('stg_audit_monthly_reporting_run_health') }}
