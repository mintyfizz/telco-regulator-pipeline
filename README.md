# telco-regulator-pipeline

> A local, open-source telecom regulator data platform: synthetic operator submissions, PostgreSQL bronze warehouse, MinIO object storage, and a roadmap toward validation, dbt models, and BI dashboards.

[![Status: active development](https://img.shields.io/badge/status-active%20development-orange.svg)](#project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg)](docker-compose.yml)

## Overview

Telecom regulators manage critical national data flows: subscriber counts, voice/SMS/data traffic, quality of service, revenue, coverage, complaints, and security incidents. In many contexts, these flows still arrive as spreadsheets and email attachments.

This project models what a modern regulatory data platform can look like using a local open-source stack. It is calibrated to a realistic Republic of Congo telecom market structure, but all operator names and generated submissions are fictional.

## Project Status

Implemented now:

- Docker Compose stack with PostgreSQL 16 and MinIO.
- PostgreSQL medallion schemas: `bronze`, `silver`, `gold`, and `audit`.
- Bronze tables for subscribers, voice traffic, SMS traffic, internet traffic, QoS, and revenue.
- Silver reference data for 7 fictional operators and 15 Congolese departments.
- Synthetic data generator for monthly 2020-2024 regulatory submissions.

Next:

- Upload generated CSVs into the MinIO `landing` bucket using an S3-compatible client.

Planned:

- Airflow ingestion DAGs.
- Great Expectations validation and quarantine handling.
- dbt silver/gold transformations.
- Metabase dashboards for sector observatory analytics.

## What It Generates

The generator produces monthly CSV submissions across six regulatory domains:

| Domain | Bronze table | Grain |
|---|---|---|
| Subscribers | `bronze.subscribers` | operator, period, department, service segment |
| Voice traffic | `bronze.traffic_voice` | operator, period, department |
| SMS traffic | `bronze.traffic_sms` | operator, period, department |
| Internet traffic | `bronze.traffic_internet` | operator, period, department |
| Quality of service | `bronze.qos` | operator, period, department |
| Revenue | `bronze.revenue` | operator, period |

For a full 2020-2024 run, expected row counts are:

| Domain | Rows |
|---|---:|
| `subscribers` | 14,400 |
| `traffic_voice` | 1,800 |
| `traffic_sms` | 1,800 |
| `traffic_internet` | 1,800 |
| `qos` | 1,800 |
| `revenue` | 120 |

Late-2024 generated values are calibrated around these anchors:

- About 6.05M mobile telephony subscribers.
- About 3.76M mobile internet subscribers.
- About 508M outgoing voice minutes per month.
- About 7.6B mobile internet MB per month.
- About 16B XAF total monthly revenue.

## Architecture

```mermaid
flowchart TB
    sources["Synthetic operator submissions<br/>CSV files by domain and month"]
    landing["MinIO landing bucket<br/>S3-compatible raw file storage"]
    airflow["Airflow ingestion DAGs<br/>planned"]
    bronze["PostgreSQL bronze<br/>raw rows + audit metadata"]
    quality["Great Expectations<br/>planned validation + quarantine"]
    silver["PostgreSQL silver<br/>cleaned and validated models"]
    gold["PostgreSQL gold<br/>analytics-ready marts"]
    bi["Metabase dashboards<br/>planned"]

    sources --> landing
    landing --> airflow
    airflow --> bronze
    bronze --> quality
    quality --> silver
    silver --> gold
    gold --> bi

    classDef implemented fill:#d8f2e3,stroke:#111827,color:#111827
    classDef planned fill:#fff6cf,stroke:#111827,color:#111827

    class sources,landing,bronze implemented
    class airflow,quality,silver,gold,bi planned
```

## Data Model

The warehouse initializes four schemas:

| Schema | Purpose |
|---|---|
| `bronze` | Raw submissions captured with audit metadata. |
| `silver` | Curated reference data now; validated models later. |
| `gold` | Future analytics-ready marts. |
| `audit` | Pipeline run and file ingestion tracking. |

The silver reference layer currently seeds:

- 7 fictional telecom operators: 2 mobile operators, 1 state-owned fixed operator, and 4 ISPs.
- 15 Congolese departments with 2023 population, area, density, zone, and urban-concentration flags.

## Quick Start

Clone the project:

```bash
git clone https://github.com/mintyfizz/telco-regulator-pipeline.git
cd telco-regulator-pipeline
```

Install Python dependencies:

```bash
uv sync
```

Start local services:

```bash
docker compose up -d
```

Available services:

| Service | URL / Port | Credentials |
|---|---|---|
| PostgreSQL | `localhost:5433` | `telco_admin` / `changeme_local_only` |
| MinIO API | `localhost:9000` | `minio_admin` / `changeme_local_only` |
| MinIO Console | `http://localhost:9001` | `minio_admin` / `changeme_local_only` |

Generate the full synthetic dataset:

```bash
uv run telco-generate --start-year 2020 --end-year 2024 --output-dir output
```

Generated files are written to:

```text
output/<domain>/<year>/<report_period>.csv
```

Example:

```text
output/traffic_sms/2020/2020-01.csv
```

Generated output is ignored by git. Keep the generator code, not generated data, under version control.

## Useful Commands

```bash
# Start services
docker compose up -d

# Show service status
docker compose ps

# Stop services
docker compose down

# Stop services and clear local volumes
docker compose down -v

# Generate synthetic data
uv run telco-generate --start-year 2020 --end-year 2024 --output-dir output
```

## Repository Layout

```text
airflow/                 Airflow DAG and plugin scaffold
data_generator/          Synthetic telecom submission generator
dbt_project/             Future dbt models and tests
docs/                    Design notes, decisions, screenshots
great_expectations/      Future data quality project
infra/postgres/init/     PostgreSQL schema and seed SQL
scripts/                 Utility scripts
docker-compose.yml       Local PostgreSQL and MinIO stack
pyproject.toml           Python package and tool configuration
uv.lock                  Locked Python dependency resolution
```

## Tech Stack

| Layer | Technology | Status |
|---|---|---|
| Synthetic data | Python, NumPy, Pydantic, Click | Implemented |
| Object storage | MinIO | Running locally |
| Warehouse | PostgreSQL 16 | Bronze implemented |
| Orchestration | Apache Airflow | Planned |
| Validation | Great Expectations | Planned |
| Transformation | dbt-core | Planned |
| BI | Metabase | Planned |
| Packaging | uv | Implemented |
| Container runtime | Docker Compose | Implemented |

## Roadmap

- [x] v0.1 - Repository structure, license, initial documentation
- [x] v0.2 - Docker Compose stack with PostgreSQL and MinIO
- [x] v0.3 - Bronze schema, audit infrastructure, and reference data
- [x] v0.4 - Synthetic data generator
- [ ] v0.5 - Upload generated CSVs to MinIO landing bucket
- [ ] v0.6 - Airflow batch ingestion DAGs
- [ ] v0.7 - Great Expectations validation and quarantine
- [ ] v0.8 - dbt staging and marts models
- [ ] v0.9 - Metabase dashboards
- [ ] v1.0 - Production-ready release with full documentation

## License

MIT - see [LICENSE](LICENSE).

## Author

Thomas Gatse - [github.com/mintyfizz](https://github.com/mintyfizz)
