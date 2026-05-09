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
  run_health,
  bronze_rows_by_domain,
  rejections_by_domain,
  validation_results,
  updated_at
FROM {{ source('audit', 'v_monthly_reporting_run_health') }}
