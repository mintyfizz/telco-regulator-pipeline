# Metabase Dashboard Delivery Plan (v1.0)

## Priority Order

1. Quality events and rejection trends
2. Coverage and QoS trends
3. Traffic and revenue trends
4. Operator comparison scorecards

## Backing Datasets

- `mart_quality_events_open`
- `mart_regulator_kpis_monthly`
- `mart_operator_scorecard_monthly`
- `mart_pipeline_run_health`

## Acceptance Criteria

- Data freshness: monthly data visible within one completed pipeline cycle.
- Filterability: period, operator, segment, and domain filters available.
- Cross-segment comparison: mobile/fixed comparisons possible in one dashboard flow.
- Exportability: chart/table export enabled for regulator reporting packs.

## Release Gate for v1.0

- All four dashboard groups published.
- At least one product owner validation pass on each dashboard group.
- No unresolved `attention` run-health issue blocking monthly data trust.
