SELECT
  silver_id,
  bronze_id,
  operator_id,
  service_segment,
  service_category,
  report_period,
  region_code,
  total_subscribers,
  active_subscribers_30d,
  arpu_xaf,
  submitted_at,
  bronze_loaded_at,
  silver_loaded_at
FROM {{ source('silver', 'subscribers') }}
