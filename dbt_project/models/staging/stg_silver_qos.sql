SELECT
  silver_id,
  bronze_id,
  operator_id,
  service_segment,
  report_period,
  region_code,
  network_availability_pct,
  avg_latency_ms,
  qos_related_complaints,
  submitted_at,
  bronze_loaded_at,
  silver_loaded_at
FROM {{ source('silver', 'qos') }}
