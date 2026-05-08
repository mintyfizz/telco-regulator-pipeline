"""
Generic ingestion logic for mobile bronze domains after subscribers.

This module handles the five remaining v1 mobile domains:
traffic_voice, traffic_sms, traffic_internet, qos, and revenue.
Each domain has its own table/columns, but the ingestion mechanics are the
same: discover CSVs in landing, validate structure, insert into bronze, move
objects to processed/quarantine, and write audit records.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from psycopg2.extras import Json

from lib.audit import (
    finish_pipeline_run,
    loaded_files_for_bucket,
    record_file_ingestion,
    start_pipeline_run,
)
from lib.minio_helpers import download_object, get_object_size, list_objects, move_object
from lib.postgres_helpers import get_warehouse_connection, insert_rows

LANDING_BUCKET = "landing"
PROCESSED_BUCKET = "processed"
QUARANTINE_BUCKET = "quarantine"
LANDING_PREFIX = "mobile/"


@dataclass(frozen=True)
class DomainConfig:
    """Configuration for loading one bronze domain table."""

    domain: str
    table_name: str
    business_columns: list[str]
    integer_columns: set[str]
    decimal_columns: set[str]
    has_region_code: bool = True

    @property
    def required_columns(self) -> set[str]:
        base = {
            "source_submission_id",
            "operator_id",
            "report_period",
            "service_segment",
            "submitted_at",
            "_raw_payload",
        }
        if self.has_region_code:
            base.add("region_code")
        return base | set(self.business_columns)

    @property
    def insert_columns(self) -> list[str]:
        columns = [
            "source_submission_id",
            "operator_id",
            "report_period",
        ]
        if self.has_region_code:
            columns.append("region_code")
        columns.append("service_segment")
        columns.extend(self.business_columns)
        columns.extend(
            [
                "submitted_at",
                "_source_file",
                "_source_line",
                "_loaded_by_run_id",
                "_raw_payload",
            ]
        )
        return columns


DOMAIN_CONFIGS: dict[str, DomainConfig] = {
    "traffic_voice": DomainConfig(
        domain="traffic_voice",
        table_name="bronze.traffic_voice",
        business_columns=[
            "voice_minutes_outgoing_onnet",
            "voice_minutes_outgoing_offnet",
            "voice_minutes_outgoing_international",
            "voice_minutes_incoming_national",
            "voice_minutes_incoming_international",
        ],
        integer_columns={
            "voice_minutes_outgoing_onnet",
            "voice_minutes_outgoing_offnet",
            "voice_minutes_outgoing_international",
            "voice_minutes_incoming_national",
            "voice_minutes_incoming_international",
        },
        decimal_columns=set(),
    ),
    "traffic_sms": DomainConfig(
        domain="traffic_sms",
        table_name="bronze.traffic_sms",
        business_columns=[
            "sms_count_outgoing_onnet",
            "sms_count_outgoing_offnet",
            "sms_count_outgoing_international",
            "sms_count_incoming_national",
        ],
        integer_columns={
            "sms_count_outgoing_onnet",
            "sms_count_outgoing_offnet",
            "sms_count_outgoing_international",
            "sms_count_incoming_national",
        },
        decimal_columns=set(),
    ),
    "traffic_internet": DomainConfig(
        domain="traffic_internet",
        table_name="bronze.traffic_internet",
        business_columns=[
            "data_consumed_mb_2g",
            "data_consumed_mb_3g",
            "data_consumed_mb_4g",
            "data_consumed_mb_5g",
        ],
        integer_columns=set(),
        decimal_columns={
            "data_consumed_mb_2g",
            "data_consumed_mb_3g",
            "data_consumed_mb_4g",
            "data_consumed_mb_5g",
        },
    ),
    "qos": DomainConfig(
        domain="qos",
        table_name="bronze.qos",
        business_columns=[
            "measurement_methodology",
            "period_type",
            "network_availability_pct",
            "call_drop_rate_pct",
            "call_setup_success_rate_pct",
            "avg_data_throughput_mbps_4g",
            "avg_data_throughput_mbps_3g",
            "avg_latency_ms",
            "population_coverage_pct_4g",
            "population_coverage_pct_3g",
            "population_coverage_pct_2g",
            "qos_related_complaints",
        ],
        integer_columns={
            "avg_latency_ms",
            "qos_related_complaints",
        },
        decimal_columns={
            "network_availability_pct",
            "call_drop_rate_pct",
            "call_setup_success_rate_pct",
            "avg_data_throughput_mbps_4g",
            "avg_data_throughput_mbps_3g",
            "population_coverage_pct_4g",
            "population_coverage_pct_3g",
            "population_coverage_pct_2g",
        },
    ),
    "revenue": DomainConfig(
        domain="revenue",
        table_name="bronze.revenue",
        business_columns=[
            "revenue_voice_outgoing_onnet_xaf",
            "revenue_voice_outgoing_offnet_xaf",
            "revenue_voice_outgoing_international_xaf",
            "revenue_voice_incoming_national_xaf",
            "revenue_voice_incoming_international_xaf",
            "revenue_sms_outgoing_onnet_xaf",
            "revenue_sms_outgoing_offnet_xaf",
            "revenue_sms_outgoing_international_xaf",
            "revenue_sms_incoming_xaf",
            "revenue_internet_2g_xaf",
            "revenue_internet_3g_xaf",
            "revenue_internet_4g_xaf",
            "revenue_internet_5g_xaf",
            "revenue_value_added_services_xaf",
            "revenue_other_xaf",
            "total_revenue_xaf",
            "usf_contribution_xaf",
        ],
        integer_columns={
            "revenue_voice_outgoing_onnet_xaf",
            "revenue_voice_outgoing_offnet_xaf",
            "revenue_voice_outgoing_international_xaf",
            "revenue_voice_incoming_national_xaf",
            "revenue_voice_incoming_international_xaf",
            "revenue_sms_outgoing_onnet_xaf",
            "revenue_sms_outgoing_offnet_xaf",
            "revenue_sms_outgoing_international_xaf",
            "revenue_sms_incoming_xaf",
            "revenue_internet_2g_xaf",
            "revenue_internet_3g_xaf",
            "revenue_internet_4g_xaf",
            "revenue_internet_5g_xaf",
            "revenue_value_added_services_xaf",
            "revenue_other_xaf",
            "total_revenue_xaf",
            "usf_contribution_xaf",
        },
        decimal_columns=set(),
        has_region_code=False,
    ),
}


class ValidationError(Exception):
    """Raised when a mobile domain CSV is structurally invalid."""


def start_mobile_domains_run(dag_id: str, run_type: str = "scheduled") -> str:
    """Create the run-level audit row for multi-domain mobile ingestion."""
    return start_pipeline_run(
        dag_id=dag_id,
        task_id="bronze_mobile_domains_ingestion",
        run_type=run_type,
    )


def discover_mobile_domain_files(domains: list[str] | None = None) -> list[str]:
    """Discover new landing CSVs for configured mobile domains."""
    allowed_domains = set(domains or DOMAIN_CONFIGS)
    keys = list_objects(LANDING_BUCKET, prefix=LANDING_PREFIX)
    loaded_files = loaded_files_for_bucket(LANDING_BUCKET)
    candidates: list[str] = []

    for key in sorted(keys):
        if not key.endswith(".csv"):
            continue
        try:
            parsed = _parse_mobile_key(key)
        except ValidationError:
            continue
        if parsed["domain"] not in allowed_domains:
            continue
        if key in loaded_files:
            continue
        candidates.append(key)

    return candidates


def process_mobile_domain_file(file_key: str, run_id: str) -> dict[str, Any]:
    """Process one non-subscriber mobile domain CSV from landing."""
    parsed_key = _safe_parse_key(file_key)
    domain = parsed_key.get("domain", "unknown")
    config = DOMAIN_CONFIGS.get(domain)

    try:
        if config is None:
            raise ValidationError(f"Unsupported domain: {domain}")

        parsed_key = _parse_mobile_key(file_key)
        file_size = get_object_size(LANDING_BUCKET, file_key)
        content = download_object(LANDING_BUCKET, file_key)
        checksum = hashlib.sha256(content).hexdigest()

        raw_rows = _read_csv(content, config)
        insert_rows_payload = _build_insert_rows(
            raw_rows=raw_rows,
            file_key=file_key,
            run_id=run_id,
            expected_operator_id=parsed_key["operator_id"],
            expected_service_segment=parsed_key["service_segment"],
            config=config,
        )
    except Exception as exc:
        return _quarantine_file(
            file_key=file_key,
            run_id=run_id,
            domain=domain,
            file_size_bytes=_safe_get_object_size(file_key),
            rows_total=0,
            reason=str(exc),
        )

    try:
        with get_warehouse_connection() as conn:
            try:
                rows_loaded = insert_rows(
                    table_name=config.table_name,
                    columns=config.insert_columns,
                    rows=insert_rows_payload,
                    conn=conn,
                )
                move_object(
                    source_bucket=LANDING_BUCKET,
                    source_key=file_key,
                    dest_bucket=PROCESSED_BUCKET,
                    dest_key=file_key,
                    additional_metadata={
                        "ingestion-status": "loaded",
                        "loaded-by-run-id": run_id,
                        "rows-loaded": str(rows_loaded),
                    },
                )
                record_file_ingestion(
                    run_id=run_id,
                    source_file=file_key,
                    source_bucket=LANDING_BUCKET,
                    data_domain=config.domain,
                    operator_id=parsed_key["operator_id"],
                    status="loaded",
                    file_size_bytes=file_size,
                    rows_total=len(raw_rows),
                    rows_loaded=rows_loaded,
                    rows_quarantined=0,
                    report_period=parsed_key["report_period"],
                    file_checksum_sha256=checksum,
                    conn=conn,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return {
            "file_key": file_key,
            "domain": config.domain,
            "status": "loaded",
            "rows_total": len(raw_rows),
            "rows_loaded": rows_loaded,
            "rows_quarantined": 0,
            "error_message": None,
        }
    except Exception as exc:
        return _quarantine_file(
            file_key=file_key,
            run_id=run_id,
            domain=config.domain,
            file_size_bytes=file_size,
            rows_total=len(raw_rows),
            reason=str(exc),
        )


def finish_mobile_domains_run(
    run_id: str,
    results: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Aggregate per-file results and close the run-level audit row."""
    results = results or []
    files_processed = len(results)
    rows_loaded = sum(int(result.get("rows_loaded") or 0) for result in results)
    rows_failed = sum(int(result.get("rows_quarantined") or 0) for result in results)
    failed_files = [result for result in results if result.get("status") != "loaded"]

    status = "success" if not failed_files else "failed"
    error_message = None
    if failed_files:
        error_message = f"{len(failed_files)} mobile domain file(s) failed or were quarantined"

    finish_pipeline_run(
        run_id=run_id,
        status=status,
        files_processed=files_processed,
        records_processed=rows_loaded,
        records_failed=rows_failed,
        error_message=error_message,
    )

    return {
        "run_id": run_id,
        "status": status,
        "files_processed": files_processed,
        "rows_loaded": rows_loaded,
        "rows_failed": rows_failed,
        "failed_files": len(failed_files),
    }


def _parse_mobile_key(key: str) -> dict[str, str]:
    parts = key.split("/")
    if len(parts) != 6:
        raise ValidationError(
            "Expected key format: mobile/<operator>/<domain>/<year>/<month>/<file>.csv"
        )

    service_segment, operator_id, domain, year, month, filename = parts
    if service_segment != "mobile":
        raise ValidationError(f"v1 ingestion only supports mobile, got {service_segment}")
    if domain not in DOMAIN_CONFIGS:
        raise ValidationError(f"Unsupported domain: {domain}")
    if not filename.endswith(".csv"):
        raise ValidationError("Object is not a CSV file")

    return {
        "service_segment": service_segment,
        "operator_id": operator_id,
        "domain": domain,
        "year": year,
        "month": month,
        "report_period": f"{year}-{month}",
        "filename": filename,
    }


def _read_csv(content: bytes, config: DomainConfig) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValidationError("CSV has no header row")

    missing = config.required_columns - set(reader.fieldnames)
    if missing:
        raise ValidationError(f"CSV is missing required columns: {sorted(missing)}")

    rows: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ValidationError(f"CSV row {row_number} has extra fields")
        rows.append(row)

    if not rows:
        raise ValidationError("CSV has no data rows")

    return rows


def _build_insert_rows(
    raw_rows: list[dict[str, str]],
    file_key: str,
    run_id: str,
    expected_operator_id: str,
    expected_service_segment: str,
    config: DomainConfig,
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []

    for source_line, row in enumerate(raw_rows, start=2):
        if row["operator_id"] != expected_operator_id:
            raise ValidationError(
                f"Row {source_line} operator_id={row['operator_id']} does not match path operator"
            )
        if row["service_segment"] != expected_service_segment:
            raise ValidationError(
                f"Row {source_line} service_segment={row['service_segment']} does not match path segment"
            )

        raw_payload = _parse_json(row["_raw_payload"], source_line)
        values: list[Any] = [
            _clean_string(row["source_submission_id"]),
            _clean_string(row["operator_id"]),
            _clean_string(row["report_period"]),
        ]

        if config.has_region_code:
            values.append(_clean_string(row["region_code"]))

        values.append(_clean_string(row["service_segment"]))

        for column in config.business_columns:
            values.append(_parse_column_value(row.get(column), column, source_line, config))

        values.extend(
            [
                _clean_string(row["submitted_at"]),
                file_key,
                source_line,
                run_id,
                Json(raw_payload),
            ]
        )
        rows.append(tuple(values))

    return rows


def _quarantine_file(
    file_key: str,
    run_id: str,
    domain: str,
    file_size_bytes: int,
    rows_total: int,
    reason: str,
) -> dict[str, Any]:
    parsed_key = _safe_parse_key(file_key)
    try:
        with get_warehouse_connection() as conn:
            try:
                move_object(
                    source_bucket=LANDING_BUCKET,
                    source_key=file_key,
                    dest_bucket=QUARANTINE_BUCKET,
                    dest_key=file_key,
                    additional_metadata={
                        "ingestion-status": "quarantined",
                        "quarantine-reason": reason[:500],
                        "loaded-by-run-id": run_id,
                    },
                )
                record_file_ingestion(
                    run_id=run_id,
                    source_file=file_key,
                    source_bucket=LANDING_BUCKET,
                    data_domain=domain,
                    operator_id=parsed_key.get("operator_id", "UNKNOWN"),
                    status="quarantined",
                    file_size_bytes=file_size_bytes,
                    rows_total=rows_total,
                    rows_loaded=0,
                    rows_quarantined=rows_total,
                    report_period=parsed_key.get("report_period"),
                    error_message=reason[:1000],
                    conn=conn,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
    except Exception as quarantine_error:
        return {
            "file_key": file_key,
            "domain": domain,
            "status": "failed",
            "rows_total": rows_total,
            "rows_loaded": 0,
            "rows_quarantined": rows_total,
            "error_message": (
                f"{reason}; additionally failed to quarantine: {quarantine_error}"
            ),
        }

    return {
        "file_key": file_key,
        "domain": domain,
        "status": "quarantined",
        "rows_total": rows_total,
        "rows_loaded": 0,
        "rows_quarantined": rows_total,
        "error_message": reason,
    }


def _safe_parse_key(file_key: str) -> dict[str, str]:
    try:
        return _parse_mobile_key(file_key)
    except ValidationError:
        return {
            "operator_id": "UNKNOWN",
            "domain": "unknown",
            "report_period": None,
        }


def _safe_get_object_size(file_key: str) -> int:
    try:
        return get_object_size(LANDING_BUCKET, file_key)
    except Exception:
        return 0


def _clean_string(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


def _parse_column_value(
    value: str | None,
    column: str,
    source_line: int,
    config: DomainConfig,
) -> Any:
    if column in config.integer_columns:
        return _parse_int(value, column, source_line)
    if column in config.decimal_columns:
        return _parse_decimal(value, column, source_line)
    return _clean_string(value)


def _parse_int(value: str | None, column: str, source_line: int) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValidationError(
            f"Row {source_line} column {column} must be an integer"
        ) from exc


def _parse_decimal(value: str | None, column: str, source_line: int) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError(
            f"Row {source_line} column {column} must be numeric"
        ) from exc


def _parse_json(value: str | None, source_line: int) -> dict[str, Any]:
    if value is None or value == "":
        raise ValidationError(f"Row {source_line} _raw_payload is required")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Row {source_line} _raw_payload is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise ValidationError(f"Row {source_line} _raw_payload must be a JSON object")
    return parsed
