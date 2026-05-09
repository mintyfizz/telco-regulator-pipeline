# Release Note: v0.9.1 Stabilization Checkpoint

This release is the official pre-v1.0 scope lock.

## Purpose

- Freeze reliability and security baseline before dashboard/product expansion.
- Ensure every change passes strict quality gates before merge.
- Provide run-level observability and triage tooling for monthly operations.

## Baseline Evidence

Required gate evidence for this checkpoint:

1. `make lint`
2. `make test`
3. `docker exec telco_airflow_scheduler airflow dags list-import-errors`

## Included in v0.9.1

- Stabilization entry criteria and reliability-first definition of done.
- Monthly run metrics persistence and run-health operational view.
- Operations runbook for monthly triage.
- Configuration contract and production security profile.
- Dashboard and alert policy plans for v1.0 execution.

## Scope Lock

No new feature/domain scope should merge unless all baseline gates are green.
Execution order remains mandatory:

1. Reliability gaps
2. Security/config hardening
3. Observability/performance
4. Dashboards + alert operations
5. New domains/segments

## Tagging

Checkpoint tag target: `v0.9.1`

If a new stabilization patch is needed, use patch tags (`v0.9.2`, `v0.9.3`, ...), and keep v1.0 feature scope gated by the same baseline checks.

