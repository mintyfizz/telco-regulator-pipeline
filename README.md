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
    subgraph data_sources["DATA SOURCES"]
        direction TB
        telco["Telco Systems<br/>(Billing, Network, Finance, SOC)"]
        complaints["ARPCE Complaints System"]
    end

    subgraph ingestion_group["INGESTION"]
        direction LR
        airflow["Airflow"]
        python["Python Pipelines"]
    end

    subgraph lake_group["DATA LAKE"]
        direction LR
        minio["MinIO<br/>Bronze Layer"]
        quarantine["Quarantine"]
    end

    subgraph processing_group["PROCESSING"]
        direction LR
        expectations["Great Expectations"]
        dbt["dbt / SQL / Python"]
    end

    subgraph warehouse_group["WAREHOUSE"]
        direction LR
        postgres["PostgreSQL<br/>Silver Layer"]
        gold["Gold Layer"]
    end

    subgraph analytics_group["ANALYTICS"]
        direction LR
        logic["Business Logic"]
        dashboard["Metabase / BI"]
    end

    telco --> python
    complaints --> python
    airflow --> python
    python --> minio
    minio -- invalid data --> quarantine
    minio --> dbt
    expectations --> dbt
    dbt --> postgres
    postgres --> gold
    gold --> logic
    logic --> dashboard
    airflow --> dbt

    classDef source fill:#bfe8f4,stroke:#111827,color:#111827
    classDef ingestion fill:#8eea8f,stroke:#111827,color:#111827
    classDef lake fill:#ffa500,stroke:#111827,color:#111827
    classDef processing fill:#d98bd3,stroke:#111827,color:#111827
    classDef warehouse fill:#fffde7,stroke:#111827,color:#111827
    classDef analytics fill:#f7a9b8,stroke:#111827,color:#111827

    class telco,complaints source
    class airflow,python ingestion
    class minio,quarantine lake
    class expectations,dbt processing
    class postgres,gold warehouse
    class logic,dashboard analytics

    style data_sources fill:#ffffff,stroke:#b7ddea,stroke-width:1px
    style ingestion_group fill:#ffffff,stroke:#94f49d,stroke-width:1px
    style lake_group fill:#ffffff,stroke:#ffa500,stroke-width:1px
    style processing_group fill:#ffffff,stroke:#f0a4ee,stroke-width:1px
    style warehouse_group fill:#ffffff,stroke:#f4efd0,stroke-width:1px
    style analytics_group fill:#ffffff,stroke:#ffb3bd,stroke-width:1px
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
