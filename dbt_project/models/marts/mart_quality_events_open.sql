select
  report_period,
  domain,
  severity,
  operator_id,
  service_segment,
  event_code,
  count(*) as open_event_count
from {{ ref('stg_silver_data_quality_events') }}
where status in ('open', 'acknowledged')
group by 1,2,3,4,5,6
