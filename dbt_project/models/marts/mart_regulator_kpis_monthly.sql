WITH subscribers AS (
  SELECT
    report_period,
    operator_id,
    service_segment,
    SUM(total_subscribers) AS total_subscribers,
    SUM(active_subscribers_30d) AS active_subscribers_30d,
    AVG(arpu_xaf) AS avg_arpu_xaf
  FROM {{ ref('stg_silver_subscribers') }}
  GROUP BY 1,2,3
),
revenue AS (
  SELECT
    report_period,
    operator_id,
    service_segment,
    SUM(total_revenue_xaf) AS total_revenue_xaf,
    SUM(usf_contribution_xaf) AS total_usf_contribution_xaf
  FROM {{ ref('stg_silver_revenue') }}
  GROUP BY 1,2,3
),
qos AS (
  SELECT
    report_period,
    operator_id,
    service_segment,
    AVG(network_availability_pct) AS avg_network_availability_pct,
    AVG(avg_latency_ms) AS avg_latency_ms,
    SUM(qos_related_complaints) AS qos_related_complaints
  FROM {{ ref('stg_silver_qos') }}
  GROUP BY 1,2,3
),
events AS (
  SELECT
    report_period,
    operator_id,
    service_segment,
    COUNT(*) FILTER (WHERE status IN ('open', 'acknowledged')) AS open_events,
    COUNT(*) FILTER (
      WHERE severity = 'critical' AND status IN ('open', 'acknowledged')
    ) AS open_critical_events
  FROM {{ ref('stg_silver_data_quality_events') }}
  GROUP BY 1,2,3
)
SELECT
  COALESCE(s.report_period, r.report_period, q.report_period, e.report_period) AS report_period,
  COALESCE(s.operator_id, r.operator_id, q.operator_id, e.operator_id) AS operator_id,
  COALESCE(s.service_segment, r.service_segment, q.service_segment, e.service_segment) AS service_segment,
  COALESCE(s.total_subscribers, 0) AS total_subscribers,
  COALESCE(s.active_subscribers_30d, 0) AS active_subscribers_30d,
  s.avg_arpu_xaf,
  COALESCE(r.total_revenue_xaf, 0) AS total_revenue_xaf,
  COALESCE(r.total_usf_contribution_xaf, 0) AS total_usf_contribution_xaf,
  q.avg_network_availability_pct,
  q.avg_latency_ms,
  COALESCE(q.qos_related_complaints, 0) AS qos_related_complaints,
  COALESCE(e.open_events, 0) AS open_quality_events,
  COALESCE(e.open_critical_events, 0) AS open_critical_quality_events
FROM subscribers s
FULL OUTER JOIN revenue r
  ON s.report_period = r.report_period
 AND s.operator_id = r.operator_id
 AND s.service_segment = r.service_segment
FULL OUTER JOIN qos q
  ON COALESCE(s.report_period, r.report_period) = q.report_period
 AND COALESCE(s.operator_id, r.operator_id) = q.operator_id
 AND COALESCE(s.service_segment, r.service_segment) = q.service_segment
FULL OUTER JOIN events e
  ON COALESCE(s.report_period, r.report_period, q.report_period) = e.report_period
 AND COALESCE(s.operator_id, r.operator_id, q.operator_id) = e.operator_id
 AND COALESCE(s.service_segment, r.service_segment, q.service_segment) = e.service_segment
