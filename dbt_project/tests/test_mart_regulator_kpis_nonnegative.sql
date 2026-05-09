SELECT *
FROM {{ ref('mart_regulator_kpis_monthly') }}
WHERE total_subscribers < 0
   OR active_subscribers_30d < 0
   OR total_revenue_xaf < 0
   OR total_usf_contribution_xaf < 0
   OR qos_related_complaints < 0
   OR open_quality_events < 0
   OR open_critical_quality_events < 0
