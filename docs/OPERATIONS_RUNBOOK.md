# Monthly Pipeline Operations Runbook

## Run Health Indicators

Use the operational view after each monthly run:

```sql
SELECT *
FROM audit.v_monthly_reporting_run_health
ORDER BY validation_started_at DESC
LIMIT 12;
```

Health interpretation:
- `healthy`: no rejections, no threshold alerts.
- `watch`: suspicious events captured but no rejection/alert breach.
- `attention`: rejections and/or threshold alerts present.

## Triage Queries

### 1) Domain-level impact for a period

```sql
SELECT
  report_period,
  jsonb_each_text(bronze_rows_by_domain) AS bronze_rows,
  jsonb_each_text(rejections_by_domain) AS rejected_rows
FROM audit.monthly_reporting_run_metrics
WHERE report_period = '2025-03';
```

### 2) Open quality events by operator/domain

```sql
SELECT
  report_period,
  operator_id,
  domain,
  severity,
  COUNT(*) AS open_events
FROM silver.data_quality_events
WHERE status IN ('open', 'acknowledged')
GROUP BY 1,2,3,4
ORDER BY open_events DESC;
```

### 3) Rejections by operator/domain/period

```sql
SELECT
  b.report_period,
  b.operator_id,
  'subscribers' AS domain,
  COUNT(*) AS rejected_rows
FROM silver.subscribers_rejections r
JOIN bronze.subscribers b ON b.bronze_id = r.bronze_id
GROUP BY 1,2
UNION ALL
SELECT
  b.report_period,
  b.operator_id,
  'traffic_voice',
  COUNT(*)
FROM silver.traffic_voice_rejections r
JOIN bronze.traffic_voice b ON b.bronze_id = r.bronze_id
GROUP BY 1,2
ORDER BY report_period DESC, rejected_rows DESC;
```

## Monthly Acceptance Checklist

- `make lint` and `make test` green.
- `airflow dags list-import-errors` returns no import errors.
- `audit.monthly_reporting_run_metrics` row exists for processed period.
- Any `attention` run is acknowledged and assigned before next schedule.
