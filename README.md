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
flowchart TB
    sources["DATA SOURCES<br/><br/>Telco Operators Systems:<br/>- Billing (Subscribers)<br/>- Network (QoS, Traffic)<br/>- Finance (Revenue)<br/>- SOC (Cybersecurity)<br/><br/>Regulator (ARPCE):<br/>- Complaints System"]
    ingestion["INGESTION LAYER<br/>Python Pipeline<br/>- API ingestion<br/>- CSV ingestion<br/>- Synthetic generation<br/><br/>Airflow DAGs<br/>- Scheduling<br/>- Dependency management"]
    lake["DATA LAKE (MinIO)<br/>Bronze Layer:<br/>- Raw, immutable data<br/>- Schema-on-read<br/><br/>Buckets:<br/>- landing/<br/>- quarantine/<br/>- processed/"]
    quality["DATA QUALITY<br/>Great Expectations<br/><br/>Checks:<br/>- Schema validation<br/>- Value ranges<br/>- Cross-field consistency"]
    processing["PROCESSING & VALIDATION<br/>Tools:<br/>- SQL / Python<br/>- dbt (future)<br/><br/>Tasks:<br/>- Cleaning<br/>- Deduplication<br/>- Type casting<br/>- Standardization"]
    warehouse["DATA WAREHOUSE (PostgreSQL)<br/><br/>Silver Layer:<br/>- Cleaned<br/>- Structured<br/>- Trusted<br/><br/>Gold Layer:<br/>- Aggregated<br/>- Analytics-ready"]
    intelligence["CROSS-DOMAIN INTELLIGENCE<br/><br/>- Subscribers to Traffic to Revenue<br/>- QoS to Complaints<br/>- Topology to Traffic<br/>- Cyber to Impact<br/><br/>Purpose:<br/>Detect anomalies & inconsistencies"]
    analytics["ANALYTICS LAYER<br/><br/>- Business logic<br/>- KPI computation<br/>- Trend analysis<br/>- Anomaly detection"]
    serving["SERVING / BI<br/><br/>Tools:<br/>- Metabase<br/>- Power BI<br/><br/>Outputs:<br/>- Dashboards<br/>- Reports<br/>- Insights"]

    sources --> ingestion --> lake --> processing --> warehouse --> intelligence --> analytics --> serving
    quality --> processing

    classDef source fill:#d8edf9,stroke:#111827,color:#111827
    classDef ingestion fill:#d8f7e6,stroke:#111827,color:#111827
    classDef lake fill:#fff6cf,stroke:#111827,color:#111827
    classDef quality fill:#f9d6d3,stroke:#111827,color:#111827
    classDef processing fill:#eadcf0,stroke:#111827,color:#111827
    classDef warehouse fill:#d8f2e3,stroke:#111827,color:#111827
    classDef intelligence fill:#f8cfa8,stroke:#111827,color:#111827
    classDef analytics fill:#e8c9ee,stroke:#111827,color:#111827
    classDef serving fill:#aee4c5,stroke:#111827,color:#111827

    class sources source
    class ingestion ingestion
    class lake lake
    class quality quality
    class processing processing
    class warehouse warehouse
    class intelligence intelligence
    class analytics analytics
    class serving serving
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

- PostgreSQL: `localhost:5433` (user: `telco_admin`, password: `changeme_local_only`, database: `telco_warehouse`)
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
