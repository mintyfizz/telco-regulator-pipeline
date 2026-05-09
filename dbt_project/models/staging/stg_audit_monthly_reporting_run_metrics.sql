SELECT
  report_period,
  validation_window_start,
  validation_started_at,
  rows_ingested,
  rows_processed,
  rows_validated,
  rows_rejected,
  events_captured,
  alerts_triggered,
  bronze_rows_by_domain,
  rejections_by_domain,
  validation_results,
  created_at,
  updated_at
FROM {{ source('audit', 'monthly_reporting_run_metrics') }}
