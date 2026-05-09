## Summary

-

## Stabilization Gate (required)

- [ ] `make lint` is green
- [ ] `make test` is green
- [ ] `docker exec telco_airflow_scheduler airflow dags list-import-errors` is clean

## Reliability-First DoD (required when behavior changes)

### Data generation
- [ ] Deterministic behavior preserved for fixed seed/period
- [ ] Output path/format contract unchanged or documented
- [ ] Tests cover new decision branches and invalid input paths

### Airflow orchestration
- [ ] DAG import check remains clean
- [ ] Idempotency behavior for loaded/partial/empty period states is explicit
- [ ] Run-level metrics remain persisted

### dbt modeling
- [ ] Model grain and key assumptions documented
- [ ] Business-rule data test added/updated when behavior changes
- [ ] Existing marts are not regressed for nonnegative/count consistency

## Scope sequencing confirmation

- [ ] Work follows gate order: reliability/security -> observability/performance -> dashboards/alerts -> new domains
- [ ] No new-domain expansion introduced before v1.0 dashboard + alert operations are stable

## Validation Evidence

Paste command outputs or links:

- Lint:
- Tests:
- DAG import check:

