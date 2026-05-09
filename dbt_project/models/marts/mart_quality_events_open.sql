SELECT
  report_period,
  domain,
  severity,
  operator_id,
  service_segment,
  event_code,
  COUNT(*) AS open_event_count
FROM {{ ref('stg_silver_data_quality_events') }}
WHERE status IN ('open', 'acknowledged')
GROUP BY 1,2,3,4,5,6
