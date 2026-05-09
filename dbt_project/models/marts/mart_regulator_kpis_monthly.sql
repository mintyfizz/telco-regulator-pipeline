with subscribers as (
  select
    report_period,
    operator_id,
    service_segment,
    sum(total_subscribers) as total_subscribers,
    sum(active_subscribers_30d) as active_subscribers_30d,
    avg(arpu_xaf) as avg_arpu_xaf
  from {{ ref('stg_silver_subscribers') }}
  group by 1,2,3
),
revenue as (
  select
    report_period,
    operator_id,
    service_segment,
    sum(total_revenue_xaf) as total_revenue_xaf,
    sum(usf_contribution_xaf) as total_usf_contribution_xaf
  from {{ ref('stg_silver_revenue') }}
  group by 1,2,3
),
qos as (
  select
    report_period,
    operator_id,
    service_segment,
    avg(network_availability_pct) as avg_network_availability_pct,
    avg(avg_latency_ms) as avg_latency_ms,
    sum(qos_related_complaints) as qos_related_complaints
  from {{ ref('stg_silver_qos') }}
  group by 1,2,3
),
events as (
  select
    report_period,
    operator_id,
    service_segment,
    count(*) filter (where status in ('open', 'acknowledged')) as open_events,
    count(*) filter (where severity = 'critical' and status in ('open', 'acknowledged')) as open_critical_events
  from {{ ref('stg_silver_data_quality_events') }}
  group by 1,2,3
)
select
  coalesce(s.report_period, r.report_period, q.report_period, e.report_period) as report_period,
  coalesce(s.operator_id, r.operator_id, q.operator_id, e.operator_id) as operator_id,
  coalesce(s.service_segment, r.service_segment, q.service_segment, e.service_segment) as service_segment,
  coalesce(s.total_subscribers, 0) as total_subscribers,
  coalesce(s.active_subscribers_30d, 0) as active_subscribers_30d,
  s.avg_arpu_xaf,
  coalesce(r.total_revenue_xaf, 0) as total_revenue_xaf,
  coalesce(r.total_usf_contribution_xaf, 0) as total_usf_contribution_xaf,
  q.avg_network_availability_pct,
  q.avg_latency_ms,
  coalesce(q.qos_related_complaints, 0) as qos_related_complaints,
  coalesce(e.open_events, 0) as open_quality_events,
  coalesce(e.open_critical_events, 0) as open_critical_quality_events
from subscribers s
full outer join revenue r
  on s.report_period = r.report_period
 and s.operator_id = r.operator_id
 and s.service_segment = r.service_segment
full outer join qos q
  on coalesce(s.report_period, r.report_period) = q.report_period
 and coalesce(s.operator_id, r.operator_id) = q.operator_id
 and coalesce(s.service_segment, r.service_segment) = q.service_segment
full outer join events e
  on coalesce(s.report_period, r.report_period, q.report_period) = e.report_period
 and coalesce(s.operator_id, r.operator_id, q.operator_id) = e.operator_id
 and coalesce(s.service_segment, r.service_segment, q.service_segment) = e.service_segment
