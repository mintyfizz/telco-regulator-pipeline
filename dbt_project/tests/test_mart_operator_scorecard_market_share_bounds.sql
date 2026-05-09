SELECT *
FROM {{ ref('mart_operator_scorecard_monthly') }}
WHERE subscriber_market_share_pct < 0
   OR subscriber_market_share_pct > 100
   OR revenue_market_share_pct < 0
   OR revenue_market_share_pct > 100
