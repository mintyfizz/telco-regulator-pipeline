# telco-regulator-pipeline

> A local, open-source telecom regulator data platform: synthetic operator submissions, PostgreSQL bronze warehouse, MinIO object storage, and a roadmap toward validation, dbt models, and BI dashboards.

[![Status: active development](https://img.shields.io/badge/status-active%20development-orange.svg)](#project-status)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker Compose](https://img.shields.io/badge/docker-compose-2496ED.svg)](docker-compose.yml)

## Overview

Telecom regulators manage critical national data flows: subscriber counts, voice/SMS/data traffic, quality of service, revenue, coverage, complaints, and security incidents. In many contexts, these flows still arrive as spreadsheets and email attachments.

This project models what a modern regulatory data platform can look like using a local open-source stack. It is calibrated to a realistic Republic of Congo telecom market structure, but all operator names and generated submissions are fictional.

## Scope and Calibration

This project implements a regulator-side data platform for the Congolese telecommunications sector. ARPCE-style regulatory scope covers multiple operator segments; this implementation currently models three:

| Segment | Operators in v1 | Calibration source |
|---|---|---|
| Mobile | OPA01, OPA02 | ARPCE 2024-style published mobile market reports |
| Fixed voice | OPA03 | Synthetic estimate, not externally calibrated |
| Fixed broadband | OPA03-OPA07 | Synthetic estimate, not externally calibrated |

The mobile segment is calibrated against published-style 2024 mobile telephony and mobile internet anchors. Generated subscriber counts, traffic volumes, and revenue figures are designed to stay close to those market totals.

The fixed voice and fixed broadband segments are architecturally complete but empirically uncalibrated. They use internally consistent synthetic values so the platform can exercise realistic multi-segment intake, validation, and analytics flows without pretending those fixed-segment numbers came from public reports.

This asymmetry is intentional: the architecture supports multi-segment regulation, while the data quality reflects the available calibration evidence.

### Segment Roadmap

- [x] Mobile - calibrated to ARPCE-style 2024 mobile market anchors
- [x] Fixed voice and fixed broadband - synthetic, architecturally complete
- [ ] Calibrate fixed segments against ITU or World Bank ICT indicators
- [ ] Postal segment
- [ ] Satellite segment
- [ ] Cybersecurity incident reporting across segments

## Project Status

Implemented now:

- Docker Compose stack with PostgreSQL 16, MinIO, and Apache Airflow.
- PostgreSQL medallion schemas: `bronze`, `silver`, `gold`, and `audit`.
- Bronze tables for subscribers, voice traffic, SMS traffic, internet traffic, QoS, and revenue.
- Silver reference data for 7 fictional operators and 15 Congolese departments.
- Synthetic data generator for monthly 2020-2024 regulatory submissions across mobile, fixed voice, and fixed broadband segments.
- MinIO upload flow using segment-aware object paths.
- Airflow bronze ingestion DAGs with audit logging and processed/quarantine file movement.

Next:

- Great Expectations validation and quarantine rules on top of bronze data.

Planned:

- dbt silver/gold transformations.
- Metabase dashboards for sector observatory analytics.

## What It Generates

The generator produces monthly CSV submissions across six regulatory domains:

| Domain | Bronze table | Grain |
|---|---|---|
| Subscribers | `bronze.subscribers` | operator, period, department, service segment |
| Voice traffic | `bronze.traffic_voice` | operator, period, department, service segment |
| SMS traffic | `bronze.traffic_sms` | operator, period, department, mobile segment |
| Internet traffic | `bronze.traffic_internet` | operator, period, department, service segment |
| Quality of service | `bronze.qos` | operator, period, department, service segment |
| Revenue | `bronze.revenue` | operator, period, service segment |

Covered service segments:

| Segment | Operators | Domains |
|---|---:|---|
| `mobile` | 2 | subscribers, voice, SMS, internet, QoS, revenue |
| `fixed_voice` | 1 | subscribers, voice, QoS, revenue |
| `fixed_broadband` | 5 | subscribers, internet, QoS, revenue |

For a full 2020-2024 run, expected row counts are:

| Domain | Rows |
|---|---:|
| `subscribers` | 19,800 |
| `traffic_voice` | 2,700 |
| `traffic_sms` | 1,800 |
| `traffic_internet` | 6,300 |
| `qos` | 7,200 |
| `revenue` | 480 |

Late-2024 generated values are calibrated around these anchors:

- About 6.05M mobile telephony subscribers.
- About 3.76M mobile internet subscribers.
- About 508M outgoing voice minutes per month.
- About 7.6B mobile internet MB per month.
- About 16B XAF total monthly revenue.
- Fixed voice and fixed broadband submissions are synthetic but segment-aware, so non-mobile operators do not submit mobile-only SMS or mobile radio metrics.

## Architecture

```mermaid
flowchart TB
    sources["Synthetic operator submissions<br/>CSV files by domain and month"]
    landing["MinIO landing bucket<br/>S3-compatible raw file storage"]
    airflow["Airflow ingestion DAGs<br/>load to bronze + audit"]
    bronze["PostgreSQL bronze<br/>raw rows + audit metadata"]
    quality["Great Expectations<br/>planned validation"]
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

    class sources,landing,airflow,bronze implemented
    class quality,silver,gold,bi planned
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
- Service-segment licensing for each operator: `mobile`, `fixed_voice`, or `fixed_broadband`.

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
| Airflow UI | `http://localhost:8080` | `admin` / `admin` |

Generate the full synthetic dataset:

```bash
uv run telco-generate generate --start-year 2020 --end-year 2024 --output-dir output
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

Upload generated files to MinIO:

```bash
uv run telco-generate upload --output-dir output/
```

The upload command writes segment-aware object keys:

```text
landing/<service_segment>/<operator_id>/<domain>/<year>/<month>/<domain>_<period>.csv
```

Run the bronze ingestion DAGs:

```bash
docker exec telco_airflow_scheduler airflow dags unpause bronze_subscribers_ingestion
docker exec telco_airflow_scheduler airflow dags unpause bronze_segment_domains_ingestion

docker exec telco_airflow_scheduler airflow dags trigger bronze_subscribers_ingestion
docker exec telco_airflow_scheduler airflow dags trigger bronze_segment_domains_ingestion
```

After a successful full ingestion, expected storage state is:

```text
landing:    0 objects
processed:  2,160 objects
quarantine: 0 objects
```

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
uv run telco-generate generate --start-year 2020 --end-year 2024 --output-dir output

# Upload generated data to MinIO landing
uv run telco-generate upload --output-dir output/

# Verify MinIO object counts
uv run telco-generate verify

# Check Airflow DAG import errors
docker exec telco_airflow_scheduler airflow dags list-import-errors
```

## Repository Layout

```text
airflow/                 Airflow DAGs and ingestion helper library
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
| Orchestration | Apache Airflow | Bronze ingestion implemented |
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
- [x] v0.5 - Upload generated CSVs to MinIO landing bucket
- [x] v0.6 - Airflow batch ingestion DAGs
- [ ] v0.7 - Great Expectations validation and quarantine
- [ ] v0.8 - dbt staging and marts models
- [ ] v0.9 - Metabase dashboards
- [ ] v1.0 - Production-ready release with full documentation

## License

MIT - see [LICENSE](LICENSE).

## Author

Thomas Gatse - [github.com/mintyfizz](https://github.com/mintyfizz)
