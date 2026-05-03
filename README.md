# telco-regulator-pipeline

> Open-source reference data platform for telecoms sector regulation. Demonstrates batch and streaming ingestion of operator submissions, automated data quality validation, multi-layer transformations, and self-service analytics — built on the modern open-source data stack.

[![Status: early development](https://img.shields.io/badge/status-early%20development-orange.svg)](#project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg)](docker-compose.yml)

## Why this exists

Telecoms regulators worldwide manage critical national data flows — operator subscriber counts, traffic, quality of service, revenue, network coverage, security incidents — but most still operate this data infrastructure with Excel and email. This project is a reference implementation of what a modern, reproducible, fully open-source regulatory data platform looks like, calibrated to a realistic emerging-market context.

## What it does

- Simulates monthly regulatory submissions from 8 fictional telecom operators across 12 administrative regions
- Ingests structured data into a medallion-architecture warehouse (bronze, silver, gold)
- Validates incoming data against declarative quality rules
- Transforms raw submissions into business-ready analytical models
- Serves dashboards for sector observatories and internal regulatory analytics
- Runs end-to-end on a single laptop via Docker Compose

## Architecture

```mermaid
flowchart LR
    orchestration["Orchestration<br/>Airflow DAGs"]
    sources["Data Sources<br/>(Telco Operators + ARPCE)<br/>- Subscribers<br/>- Traffic<br/>- QoS<br/>- Revenue<br/>- Topology<br/>- Complaints<br/>- Cyber"]
    ingestion["Ingestion Layer<br/>Python Scripts<br/>(later Airflow)"]
    lake["MinIO (Data Lake)<br/>Bronze Layer<br/>landing / quarantine / processed"]
    quality["Data Quality<br/>Great Expectations"]
    processing["Processing Layer<br/>Python + SQL<br/>(later dbt)"]
    warehouse["PostgreSQL Warehouse<br/>Bronze / Silver / Gold"]
    analytics["Analytics Layer<br/>dbt Models<br/>Validation + Business Logic"]
    dashboard["BI / Dashboard<br/>Metabase / Power BI"]

    sources --> ingestion --> lake --> processing --> warehouse --> analytics --> dashboard
    quality --> processing
    quality --> analytics
    orchestration --> ingestion
    orchestration --> processing
    orchestration --> analytics

    classDef orchestration fill:#f3f9ec,stroke:#111827,color:#111827
    classDef source fill:#e4f2ff,stroke:#111827,color:#111827
    classDef ingest fill:#e8f5e9,stroke:#111827,color:#111827
    classDef lake fill:#fff1d6,stroke:#111827,color:#111827
    classDef quality fill:#fde8eb,stroke:#111827,color:#111827
    classDef process fill:#f6e6f2,stroke:#111827,color:#111827
    classDef warehouse fill:#e0f7fa,stroke:#111827,color:#111827
    classDef analytics fill:#fde7ee,stroke:#111827,color:#111827
    classDef dashboard fill:#f7edf8,stroke:#111827,color:#111827

    class orchestration orchestration
    class sources source
    class ingestion ingest
    class lake lake
    class quality quality
    class processing process
    class warehouse warehouse
    class analytics analytics
    class dashboard dashboard
```

## Tech stack

| Layer | Technology |
|---|---|
| Object storage | MinIO (S3-compatible) |
| Orchestration | Apache Airflow |
| Warehouse | PostgreSQL 16 |
| Transformation | dbt-core |
| Validation | Great Expectations |
| BI | Metabase |
| Streaming | Apache Kafka, Spark Structured Streaming |
| CI/CD | GitHub Actions |
| Container runtime | Docker, Docker Compose |

## Quick start

```bash
git clone https://github.com/mintyfizz/telco-regulator-pipeline.git
cd telco-regulator-pipeline
docker compose up -d
```

After ~2 minutes (first run downloads images), the stack is up:

- PostgreSQL: `localhost:5432` (user: `telco_admin`, password: `changeme_local_only`, database: `telco_warehouse`)
- MinIO API: `localhost:9000`
- MinIO Console: `localhost:9001` (user: `minio_admin`, password: `changeme_local_only`)

Stop the stack with `docker compose down`. Use `docker compose down -v` to also clear data.

## Project status

Early development. Built incrementally as a learning project documenting modern data engineering practice. See the roadmap below.

## Roadmap

- [x] v0.1 — Repository structure, license, initial documentation
- [ ] v0.2 — Docker Compose stack with PostgreSQL and MinIO
- [ ] v0.3 — Synthetic data generator
- [ ] v0.4 — Airflow batch ingestion DAGs
- [ ] v0.5 — Great Expectations validation
- [ ] v0.6 — dbt staging and marts models
- [ ] v0.7 — Metabase dashboards
- [ ] v1.0 — Production-ready release with full documentation

## License

MIT — see [LICENSE](LICENSE).

## Author

Thomas Gatse — [github.com/mintyfizz](https://github.com/mintyfizz)
