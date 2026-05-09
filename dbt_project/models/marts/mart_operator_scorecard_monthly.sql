WITH kpis AS (
  SELECT * FROM {{ ref('mart_regulator_kpis_monthly') }}
),
period_totals AS (
  SELECT
    report_period,
    service_segment,
    SUM(total_subscribers) AS segment_total_subscribers,
    SUM(total_revenue_xaf) AS segment_total_revenue_xaf
  FROM kpis
  GROUP BY 1,2
)
SELECT
  k.report_period,
  k.operator_id,
  k.service_segment,
  k.total_subscribers,
  k.active_subscribers_30d,
  k.total_revenue_xaf,
  k.avg_network_availability_pct,
  k.avg_latency_ms,
  k.qos_related_complaints,
  k.open_quality_events,
  k.open_critical_quality_events,
  CASE
    WHEN p.segment_total_subscribers = 0 THEN 0
    ELSE ROUND((k.total_subscribers::NUMERIC / p.segment_total_subscribers) * 100, 4)
  END AS subscriber_market_share_pct,
  CASE
    WHEN p.segment_total_revenue_xaf = 0 THEN 0
    ELSE ROUND((k.total_revenue_xaf::NUMERIC / p.segment_total_revenue_xaf) * 100, 4)
  END AS revenue_market_share_pct
FROM kpis k
JOIN period_totals p
  ON k.report_period = p.report_period
 AND k.service_segment = p.service_segment
