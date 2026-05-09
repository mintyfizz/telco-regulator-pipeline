# Production Profile (Security and Operations)

## Required Connections and Secrets

1. Warehouse connection (`AIRFLOW_CONN_TELCO_WAREHOUSE`)
   - Use a dedicated least-privilege database role for Airflow validation/ingestion.
2. Object storage connection (`AIRFLOW_CONN_TELCO_MINIO` or S3 equivalent)
   - Access restricted to required buckets/prefixes only.
3. Airflow metadata DB credentials (`AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`)
4. Airflow Fernet key (`AIRFLOW__CORE__FERNET_KEY`)
5. Airflow admin password (`AIRFLOW_ADMIN_PASSWORD`) managed outside source control.

## Rotation Expectations

- Rotate storage/database credentials at least quarterly.
- Rotate Airflow admin credentials on staff/role changes.
- Rotate Fernet key only with a planned encrypted-secret migration window.
- Record credential issue/rotation date in platform ops logs.

## Least-Privilege Baseline

- Airflow service accounts should not have superuser DB privileges.
- Warehouse role should be constrained to required schemas/tables/functions.
- Storage credentials should not allow bucket creation/deletion in production runtime jobs.
- Dashboards/read-only BI users should not have write access.

## Operational Readiness Requirements

- Run-level metrics table populated for every monthly period.
- DAG import check clean prior to deployment.
- Lint/test gates passing before release candidate cut.
- Documented rollback: previous image + previous migration set + paused schedules.
