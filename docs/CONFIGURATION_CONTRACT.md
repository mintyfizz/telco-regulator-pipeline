# Configuration Contract

This document defines the shared configuration contract across generator CLI, Airflow, and Docker Compose.

## Required Variables

| Variable | Used by | Required | Purpose |
|---|---|---|---|
| `TELCO_POSTGRES_PASSWORD` | compose, Airflow warehouse conn | yes | Warehouse DB password |
| `TELCO_MINIO_ROOT_USER` | compose, uploader creds mapping | yes | MinIO root/access key |
| `TELCO_MINIO_ROOT_PASSWORD` | compose, uploader creds mapping | yes | MinIO root/secret key |
| `AIRFLOW_DB_PASSWORD` | compose | yes | Airflow metadata DB password |
| `AIRFLOW_ADMIN_PASSWORD` | compose | yes | Airflow admin user password |
| `AIRFLOW__CORE__FERNET_KEY` | compose | yes | Airflow secrets encryption |
| `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` | compose | yes | Airflow metadata DB DSN |
| `AIRFLOW_CONN_TELCO_WAREHOUSE` | Airflow | yes | Warehouse connection URI |
| `AIRFLOW_CONN_TELCO_MINIO` | Airflow | yes | MinIO connection URI |
| `TELCO_MINIO_ACCESS_KEY` | CLI upload/verify | yes | MinIO access key |
| `TELCO_MINIO_SECRET_KEY` | CLI upload/verify | yes | MinIO secret key |

## Optional Variables

| Variable | Default | Used by |
|---|---|---|
| `POSTGRES_USER` | `telco_admin` | compose |
| `POSTGRES_DB` | `telco_warehouse` | compose |
| `TELCO_MINIO_ENDPOINT_URL` | `http://localhost:9000` | CLI |
| `TELCO_MINIO_REGION` | `us-east-1` | CLI/Airflow |

## Policy

- No committed runtime secrets in source-controlled config.
- Local setup must start from `.env.example` copied to `.env`.
- Airflow runtime auth must come from connection env vars (`AIRFLOW_CONN_*`) rather than hardcoded DAG values.
