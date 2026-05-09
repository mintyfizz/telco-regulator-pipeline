# Stabilization Checkpoint (Scope Freeze)

This checkpoint freezes the current baseline before opening new product scope.

## Baseline Included

- Quality gate workflow (`make lint`, `make test`).
- Monthly incremental reporting pipeline with period status handling.
- Silver incremental validation and suspicious-event capture.
- dbt staging + initial marts scaffold.

## Entry Criteria for Any New Work

Every PR must satisfy all of the following before merge:

1. `make lint` is green.
2. `make test` is green.
3. Airflow DAG import check is clean:
   - `docker exec telco_airflow_scheduler airflow dags list-import-errors`

If any criterion is red, no new feature scope starts until stability is restored.

## Definition of Done (Reliability-First)

### Data-generation changes
- [ ] Deterministic behavior preserved for fixed seed/period.
- [ ] Domain output path/format contract unchanged or explicitly documented.
- [ ] Unit tests cover new decision branches and invalid input paths.

### Airflow/orchestration changes
- [ ] DAG import check remains clean.
- [ ] Idempotency behavior for loaded/partial/empty period states remains explicit.
- [ ] Run-level metrics remain persisted for triage and dashboards.

### dbt/modeling changes
- [ ] Model grain and key assumptions documented.
- [ ] At least one business-rule data test added/updated when behavior changes.
- [ ] Existing marts are not regressed for nonnegative/count consistency.

## Scope Gate Policy

Execution order is mandatory:

1. Reliability gaps
2. Security/config hardening
3. Incremental observability/performance
4. Dashboards + alert operations
5. New domains/segments

No postal/satellite/new domain scope is opened until v1.0 dashboard and alert operations are stable in routine monthly runs.
