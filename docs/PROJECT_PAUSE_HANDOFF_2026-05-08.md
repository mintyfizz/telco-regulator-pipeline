# Project Pause Handoff - Telco Regulator Pipeline

Date: 2026-05-08
Owner: Thomas Gatse
Workspace root: /Users/thomasgatse/code/telco-regulator-pipeline

## Why This Document Exists

This document is a complete checkpoint of the project at the moment you paused work. It explains:
- what this project is trying to achieve,
- what has already been built,
- what changed in the latest session,
- what is currently running and what data exists,
- what still needs to be done,
- and exactly how to resume safely.

This is intended to be understandable even after a long break.

## Project Mission In Plain Language

The project simulates a telecom regulator data platform. Instead of waiting for real operators to submit files, it generates realistic synthetic submissions every month, ingests them into a warehouse, validates them, and prepares them for analytics.

In practical terms:
- Python generates CSV submission files for six telecom reporting domains.
- Files are uploaded to MinIO (S3-compatible object storage).
- Airflow DAGs ingest files into PostgreSQL bronze tables.
- SQL validation functions move clean rows into silver tables and bad rows into rejection tables.
- Suspicious but plausible rows are tracked in data quality events for dashboard alerting.

## High-Level Architecture

1. Synthetic generation layer
- Location: data_generator/
- Produces monthly domain CSVs by service segment.

2. Object storage layer
- Location: MinIO service in docker-compose
- Buckets: landing, processed, quarantine.

3. Orchestration layer
- Location: airflow/dags/
- Ingestion DAGs load bronze and run validation.
- Monthly orchestration DAG automates generation + upload + ingestion + validation.

4. Warehouse layer (PostgreSQL)
- bronze schema: raw intake
- silver schema: validated curated facts + rejections + quality events
- gold schema: reserved for marts (not implemented yet)
- audit schema: run-level and file-level lineage

## Repository Status Summary

Current maturity from README:
- Implemented: Docker stack, generator, MinIO upload, bronze ingestion, silver validation, monthly reporting DAG, quality event schema.
- Planned next: dbt models, BI dashboards, alert notifications.

Roadmap stage:
- v0.8 capability is in place (monthly reporting DAG with catchup/backfill behavior).
- v0.9 and beyond still pending (dbt marts, dashboards).

## Project History (From Git Timeline)

Recent historical milestones (most relevant commits):
- 3b5e2cd: initial scaffolding
- 5d550c9: Docker Compose stack with Postgres and MinIO
- f1adf34: bronze layer schema foundations
- e2c3ac3: bronze taxonomy alignment
- cab355d: data generator scaffolding/config
- a4e6570: subscribers generator
- 6218907: all six domain generators
- 498ea70: MinIO uploader and all-operator submissions
- 153b9e5: uploader hardening
- 1362400: Airflow bronze ingestion from MinIO
- a31286c (tag v0.7): multi-segment silver validation completed

Important note:
- The repository HEAD commit is still v0.7-era baseline for tracked commits.
- Current v0.8-style work exists in uncommitted working tree changes.

## Exact Working Tree State At Pause Time

Uncommitted modified files:
- README.md
- airflow/dags/lib/segment_domain_ingestion.py
- airflow/dags/lib/subscribers_ingestion.py
- airflow/requirements.txt
- data_generator/telco_generator/cli.py
- data_generator/telco_generator/config.py
- data_generator/telco_generator/orchestrator.py
- data_generator/telco_generator/utils/time.py
- docker-compose.yml
- infra/postgres/migrations/001_silver_subscribers.sql
- infra/postgres/migrations/002_silver_validation_subscribers.sql

Uncommitted new files:
- airflow/dags/lib/constants.py
- airflow/dags/monthly_reporting_pipeline.py
- data_generator/telco_generator/anomalies.py
- infra/postgres/migrations/014_silver_data_quality_events.sql
- infra/postgres/migrations/015_silver_capture_suspicious_events.sql

## What Was Added In The Latest Session

### 1) Controlled anomaly generation

Files:
- data_generator/telco_generator/anomalies.py
- data_generator/telco_generator/orchestrator.py
- data_generator/telco_generator/config.py
- data_generator/telco_generator/cli.py
- data_generator/telco_generator/utils/time.py

What changed:
- Added optional period-specific generation (YYYY-MM).
- Added anomaly_rate for controlled synthetic suspicious patterns.
- Added domain-aware anomaly mutation logic.
- Added synthetic anomaly marker into each mutated row raw payload:
  - _raw_payload._synthetic_anomaly.domain
  - _raw_payload._synthetic_anomaly.code
  - _raw_payload._synthetic_anomaly.changed_fields

Why it matters:
- You can produce realistic suspicious behavior for quality monitoring demos without corrupting the full dataset.

### 2) Monthly orchestration DAG

File:
- airflow/dags/monthly_reporting_pipeline.py

What changed:
- New DAG scheduled monthly (5th at 03:00).
- Determines previous closed month automatically.
- Generates period data (optionally with anomaly_rate).
- Uploads to MinIO.
- Triggers subscriber and segmented bronze ingestion DAGs.
- Runs silver validation and event capture function.
- Supports catchup/backfill and period-level idempotency checks.

Why it matters:
- Moves project from manual batches to recurring regulator-style monthly operations.

### 3) Shared ingestion constants cleanup

Files:
- airflow/dags/lib/constants.py
- airflow/dags/lib/subscribers_ingestion.py
- airflow/dags/lib/segment_domain_ingestion.py

What changed:
- Removed duplicate ALLOWED_SERVICE_SEGMENTS definitions.
- Centralized the constant in one module.

Why it matters:
- Reduces drift and future maintenance bugs.

### 4) Quality event model and capture path

Files:
- infra/postgres/migrations/014_silver_data_quality_events.sql
- infra/postgres/migrations/015_silver_capture_suspicious_events.sql

What changed:
- Added silver.data_quality_events schema for suspicious rows.
- Added function silver.capture_suspicious_anomaly_events.
- Function reads synthetic anomaly markers from raw payload and upserts quality events.
- Function called in monthly DAG after silver validation.

Why it matters:
- Supports anomaly monitoring dashboards without forcing strict cleansing of all unusual patterns.

### 5) Rule strategy adjustment for monitoring-first behavior

Files:
- infra/postgres/migrations/001_silver_subscribers.sql
- infra/postgres/migrations/002_silver_validation_subscribers.sql

What changed:
- Removed hard upper ARPU rejection logic.
- Kept nonnegative ARPU checks.

Why it matters:
- High-but-plausible ARPU stays in silver and can be flagged as suspicious instead of being discarded.

## Current Runtime Snapshot (Captured Today)

### Service status

docker compose services currently up:
- telco_postgres: healthy
- telco_minio: healthy
- telco_airflow_postgres: healthy
- telco_airflow_webserver: healthy
- telco_airflow_scheduler: up

Note:
- Running container image for minio still showed minio/minio:latest in docker compose ps output.
- docker-compose.yml now pins minio/minio:RELEASE.2025-10-15T17-29-55Z.
- This mismatch means container was likely started before recreate; run a recreate when resuming if you want runtime to match file config.

### Data coverage in bronze

Current period range and row totals:
- subscribers: 2020-01 to 2026-04, 25080 rows
- traffic_voice: 2020-01 to 2026-04, 3420 rows
- traffic_sms: 2020-01 to 2026-04, 2280 rows
- traffic_internet: 2020-01 to 2026-04, 7980 rows
- qos: 2020-01 to 2026-04, 9120 rows
- revenue: 2020-01 to 2026-04, 608 rows

### Silver rejection totals

Current rejected rows:
- subscribers: 42
- traffic_voice: 3
- traffic_sms: 0
- traffic_internet: 7
- qos: 0
- revenue: 3

Interpretation:
- The pipeline is intentionally catching impossible rows in a small percentage of records.
- This is expected with anomaly injection and strict integrity checks.

### Quality events currently captured

Current silver.data_quality_events counts by domain/code:
- qos complaint_spike: 17
- qos qos_degradation: 13
- qos qos_perfect_report: 16
- revenue revenue_spike: 1
- subscribers arpu_spike: 22
- subscribers subscriber_spike: 33
- traffic_internet internet_traffic_spike: 25
- traffic_sms sms_traffic_spike: 9
- traffic_sms sms_zero_outage: 2
- traffic_voice voice_traffic_spike: 8

Interpretation:
- Monitoring path is active.
- Suspicious patterns are being retained and tracked for dashboarding.

## Validation Philosophy Now In Effect

Current operating policy:

Reject (hard fail):
- impossible logic,
- hard arithmetic contradictions,
- impossible ranges,
- reference/contract violations.

Keep and flag as events:
- unusual but plausible spikes,
- complaint surges,
- high plausible ARPU,
- perfect-report style QoS suspiciousness.

This matches your stated goal: anomaly monitoring rather than strict cleansing.

## Operational Commands To Resume Later

### 1) Start or refresh services

Use:
- docker compose up -d

If you want compose image/tag changes applied (including MinIO pin):
- docker compose up -d --force-recreate minio airflow_webserver airflow_scheduler

### 2) Apply migrations

From repository root:
- make migrate

### 3) Validate DAG imports

- docker exec telco_airflow_scheduler airflow dags list-import-errors

### 4) Trigger one monthly run for a test period

- docker exec telco_airflow_scheduler airflow dags trigger monthly_reporting_pipeline --conf '{"period":"2025-03"}'

### 5) Check run status

- docker exec telco_airflow_scheduler airflow dags list-runs --dag-id monthly_reporting_pipeline --no-backfill

### 6) Verify quality events

- docker exec telco_postgres psql -U telco_admin -d telco_warehouse -c "SELECT domain, event_code, severity, count(*) FROM silver.data_quality_events GROUP BY 1,2,3 ORDER BY 1,2,3;"

## Known Technical Risks / Debt At Pause

1. Secrets still in local compose and DAG code
- Example: MinIO and Airflow credentials and connection strings are hardcoded in compose and monthly DAG.
- Recommendation: move to environment variables and Airflow connections retrieval patterns.

2. Airflow package install at container startup
- Scheduler and webserver install requirements on startup.
- This can be slow and brittle.
- Recommendation: build a custom Airflow image with pinned dependencies and constraints.

3. Quality-event capture currently focused on synthetic marker path
- It captures generated anomalies from _raw_payload markers.
- Recommendation: add non-synthetic detection rules too (production-style anomaly detectors).

4. Some architecture docs still mention old planned status
- README is updated, but future docs should align all layers with current implemented state.

## Recommended Next Phase (When You Resume)

Priority order:

1. Commit and tag the current milestone
- Commit all v0.8 + anomaly monitoring changes as one coherent feature set.
- Suggested tag: v0.8.

2. Add dashboard-ready SQL views for quality events
- Create curated views by severity, domain, operator, period.
- Include open vs resolved event lifecycle metrics.

3. Build dbt staging and marts
- Model silver facts and quality events into regulator KPI marts.
- Add tests for coverage and event trend consistency.

4. Wire alerting thresholds
- Add SQL or Airflow task that raises alert when event counts exceed thresholds.

5. Harden config/security
- Remove plaintext secrets from repo defaults.
- Use env-driven config and connection-based credentials.

## Plain-English Glossary

- Bronze: raw submitted data loaded with minimal transformation.
- Silver: cleaned and validated data suitable for analysis.
- Rejection table: rows that failed hard validation and cannot be trusted as facts.
- Quality event: suspicious row pattern that is still plausible; kept for monitoring.
- Catchup/backfill: run historical scheduled periods that were missed.
- Idempotent: safe to rerun without producing duplicates or corruption.

## Resume Checklist (Fast)

- Confirm you are in repository root.
- Run docker compose up -d.
- Run make migrate.
- Run Airflow DAG import check.
- Trigger one known period monthly run.
- Query silver.data_quality_events and silver rejection tables.
- If counts look stable, continue to dbt/dashboard phase.

---

This checkpoint reflects both repository content and live environment state observed on 2026-05-08.
