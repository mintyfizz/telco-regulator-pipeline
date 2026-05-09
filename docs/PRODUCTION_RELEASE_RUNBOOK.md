# Production Release Runbook (v1.1 Readiness)

## Scope

Operational procedure for release cut, deploy, validation, rollback, and monthly runtime SLO checks.

## Versioning and Pinning

- Airflow image tags are pinned in `docker-compose.yml`.
- Python dependency ranges are declared in `pyproject.toml`; lock updates must be reviewed with quality gates.
- dbt project version is tracked in `dbt_project/dbt_project.yml`.
- Release candidates must reference an immutable git tag.

## Release Candidate Checklist

1. `make lint` passes.
2. `make test` passes.
3. DAG import check is clean:
   - `docker exec telco_airflow_scheduler airflow dags list-import-errors`
4. Required migrations are reviewed and ordered.
5. Rollback artifacts are prepared:
   - previous image tags,
   - previous migration boundary,
   - paused schedules plan.

## Deployment Procedure

1. Pause scheduler-triggered DAGs.
2. Apply migrations in order:
   - `make migrate`
3. Deploy updated images/config.
4. Recreate Airflow runtime:
   - `docker compose up -d --force-recreate airflow_webserver airflow_scheduler`
5. Validate DAG imports and health checks.
6. Trigger one controlled monthly run for verification.
7. Resume schedules after verification.

## Rollback Procedure

1. Pause schedules immediately.
2. Revert to previous pinned image versions.
3. Revert config to previous known-good env set.
4. If needed, roll back to prior migration boundary per DBA policy.
5. Re-run DAG import check and smoke monthly trigger.
6. Record incident and root cause.

## Monthly Runtime SLOs

- **Pipeline completion SLO**: monthly run completes within agreed operational window.
- **Data freshness SLO**: KPI marts updated within one completed monthly cycle.
- **Run health SLO**: no unresolved `attention` state before next scheduled cycle.

## SLO Verification Queries

Use:

- `audit.v_monthly_reporting_run_health` for monthly health status.
- `audit.monthly_reporting_run_metrics` for ingestion/validation/rejection/alert volume.

## Incident Response

For any `attention` run:

1. Assign owner immediately.
2. Run triage queries from `docs/OPERATIONS_RUNBOOK.md`.
3. Open remediation issue linked to affected period/operator/domain.
4. Close only after rerun or explicit risk acceptance.

