select
  silver_id,
  bronze_id,
  operator_id,
  service_segment,
  report_period,
  total_revenue_xaf,
  components_sum_xaf,
  sum_check_delta_xaf,
  usf_contribution_xaf,
  usf_contribution_rate_pct,
  submitted_at,
  bronze_loaded_at,
  silver_loaded_at
from {{ source('silver', 'revenue') }}
