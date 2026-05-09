"""
Subscriber ingestion logic used by the bronze_subscribers_ingestion DAG.

The DAG file defines orchestration only. This module owns the operational work:
listing new subscriber files, validating CSV structure, inserting valid rows
into bronze.subscribers, moving files to processed or quarantine, and writing
audit records.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal, InvalidOperation
from typing import Any

from airflow.exceptions import AirflowException
from psycopg2.extras import Json
from telco_generator.ingestion_paths import PathValidationError, parse_subscriber_key

from lib.audit import (
    finalized_files_for_bucket,
    finish_pipeline_run,
    record_file_ingestion,
    start_pipeline_run,
)
from lib.constants import ALLOWED_SERVICE_SEGMENTS
from lib.minio_helpers import (
    copy_object,
    delete_object,
    download_object,
    get_object_size,
    list_objects,
)
from lib.postgres_helpers import get_warehouse_connection, insert_rows

LANDING_BUCKET = "landing"
PROCESSED_BUCKET = "processed"
QUARANTINE_BUCKET = "quarantine"
DOMAIN = "subscribers"
LANDING_PREFIX = ""

REQUIRED_COLUMNS = {
    "source_submission_id",
    "operator_id",
    "report_period",
    "region_code",
    "service_segment",
    "service_category",
    "payment_type",
    "technology_generation",
    "total_subscribers",
    "active_subscribers_30d",
    "new_activations",
    "churn_count",
    "arpu_xaf",
    "submitted_at",
    "_raw_payload",
}

INSERT_COLUMNS = [
    "source_submission_id",
    "operator_id",
    "report_period",
    "region_code",
    "service_segment",
    "service_category",
    "payment_type",
    "technology_generation",
    "total_subscribers",
    "active_subscribers_30d",
    "new_activations",
    "churn_count",
    "arpu_xaf",
    "submitted_at",
    "_source_file",
    "_source_line",
    "_loaded_by_run_id",
    "_raw_payload",
]

INTEGER_COLUMNS = {
    "total_subscribers",
    "active_subscribers_30d",
    "new_activations",
    "churn_count",
}


class ValidationError(Exception):
    """Raised when a subscriber CSV is structurally invalid."""


def start_subscribers_run(dag_id: str, run_type: str = "scheduled") -> str:
    """Create the run-level audit row for this DAG execution."""
    return start_pipeline_run(
        dag_id=dag_id,
        task_id="bronze_subscribers_ingestion",
        run_type=run_type,
    )


def discover_subscriber_files() -> list[str]:
    """
    Discover new subscriber CSVs in landing.

    Files are expected at:
    landing/<segment>/<operator>/subscribers/<year>/<month>/<file>.csv
    """
    keys = list_objects(LANDING_BUCKET, prefix=LANDING_PREFIX)
    finalized_files = finalized_files_for_bucket(LANDING_BUCKET)
    candidates: list[str] = []

    for key in sorted(keys):
        if not key.endswith(".csv"):
            continue
        try:
            parsed = _parse_subscriber_key(key)
        except ValidationError:
            continue
        if parsed["domain"] != DOMAIN:
            continue
        if key in finalized_files:
            continue
        candidates.append(key)

    return candidates


def process_subscriber_file(file_key: str, run_id: str) -> dict[str, Any]:
    """
    Process one subscriber CSV from landing.

    Returns a JSON-serializable result dict for Airflow XCom aggregation.
    """
    try:
        parsed_key = _parse_subscriber_key(file_key)
        file_size = get_object_size(LANDING_BUCKET, file_key)
        content = download_object(LANDING_BUCKET, file_key)
        checksum = hashlib.sha256(content).hexdigest()

        raw_rows = _read_csv(content)
        insert_rows_payload = _build_insert_rows(
            raw_rows=raw_rows,
            file_key=file_key,
            run_id=run_id,
            expected_operator_id=parsed_key["operator_id"],
            expected_service_segment=parsed_key["service_segment"],
        )
    except Exception as exc:
        return _quarantine_file(
            file_key=file_key,
            run_id=run_id,
            file_size_bytes=_safe_get_object_size(file_key),
            rows_total=0,
            reason=str(exc),
        )

    try:
        with get_warehouse_connection() as conn:
            try:
                rows_loaded = insert_rows(
                    table_name="bronze.subscribers",
                    columns=INSERT_COLUMNS,
                    rows=insert_rows_payload,
                    conn=conn,
                )
                copy_object(
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
                    data_domain=DOMAIN,
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

        landing_delete_error = _delete_landing_after_finalize(file_key)

        return {
            "file_key": file_key,
            "status": "loaded",
            "rows_total": len(raw_rows),
            "rows_loaded": rows_loaded,
            "rows_quarantined": 0,
            "error_message": landing_delete_error,
        }
    except Exception as exc:
        return _quarantine_file(
            file_key=file_key,
            run_id=run_id,
            file_size_bytes=file_size,
            rows_total=len(raw_rows),
            reason=str(exc),
        )


def finish_subscribers_run(run_id: str, results: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Aggregate per-file results and close the run-level audit row."""
    results = results or []
    files_processed = len(results)
    rows_loaded = sum(int(result.get("rows_loaded") or 0) for result in results)
    rows_failed = sum(int(result.get("rows_quarantined") or 0) for result in results)
    failed_files = [
        result for result in results
        if result.get("status") not in {"loaded", "skipped"}
    ]

    status = "success" if not failed_files else "failed"
    error_message = None
    if failed_files:
        error_message = f"{len(failed_files)} subscriber file(s) failed or were quarantined"

    finish_pipeline_run(
        run_id=run_id,
        status=status,
        files_processed=files_processed,
        records_processed=rows_loaded,
        records_failed=rows_failed,
        error_message=error_message,
    )

    if failed_files:
        raise AirflowException(error_message)

    return {
        "run_id": run_id,
        "status": status,
        "files_processed": files_processed,
        "rows_loaded": rows_loaded,
        "rows_failed": rows_failed,
        "failed_files": len(failed_files),
    }


def _parse_subscriber_key(key: str) -> dict[str, str]:
    try:
        parsed = parse_subscriber_key(key, allowed_service_segments=ALLOWED_SERVICE_SEGMENTS)
    except PathValidationError as exc:
        raise ValidationError(str(exc)) from exc
    return {
        "service_segment": parsed.service_segment,
        "operator_id": parsed.operator_id,
        "domain": parsed.domain,
        "year": parsed.year,
        "month": parsed.month,
        "report_period": parsed.report_period,
        "filename": parsed.filename,
    }


def _read_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValidationError("CSV has no header row")

    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
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
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []

    for source_line, row in enumerate(raw_rows, start=2):
        if row["operator_id"] != expected_operator_id:
            raise ValidationError(
                f"Row {source_line} operator_id={row['operator_id']} does not match path operator"
            )
        if row["service_segment"] != expected_service_segment:
            raise ValidationError(
                f"Row {source_line} service_segment={row['service_segment']} "
                "does not match path segment"
            )

        raw_payload = _parse_json(row["_raw_payload"], source_line)
        rows.append(
            (
                _clean_string(row["source_submission_id"]),
                _clean_string(row["operator_id"]),
                _clean_string(row["report_period"]),
                _clean_string(row["region_code"]),
                _clean_string(row["service_segment"]),
                _clean_string(row["service_category"]),
                _clean_string(row["payment_type"]),
                _clean_string(row["technology_generation"]),
                _parse_int(row["total_subscribers"], "total_subscribers", source_line),
                _parse_int(row["active_subscribers_30d"], "active_subscribers_30d", source_line),
                _parse_int(row["new_activations"], "new_activations", source_line),
                _parse_int(row["churn_count"], "churn_count", source_line),
                _parse_decimal(row["arpu_xaf"], "arpu_xaf", source_line),
                _clean_string(row["submitted_at"]),
                file_key,
                source_line,
                run_id,
                Json(raw_payload),
            )
        )

    return rows


def _quarantine_file(
    file_key: str,
    run_id: str,
    file_size_bytes: int,
    rows_total: int,
    reason: str,
) -> dict[str, Any]:
    parsed_key = _safe_parse_key(file_key)
    try:
        with get_warehouse_connection() as conn:
            try:
                copy_object(
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
                    data_domain=DOMAIN,
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
        landing_delete_error = _delete_landing_after_finalize(file_key)
    except Exception as quarantine_error:
        return {
            "file_key": file_key,
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
        "status": "quarantined",
        "rows_total": rows_total,
        "rows_loaded": 0,
        "rows_quarantined": rows_total,
        "error_message": landing_delete_error or reason,
    }


def _safe_parse_key(file_key: str) -> dict[str, str]:
    try:
        return _parse_subscriber_key(file_key)
    except ValidationError:
        return {"operator_id": "UNKNOWN", "report_period": None}


def _safe_get_object_size(file_key: str) -> int:
    try:
        return get_object_size(LANDING_BUCKET, file_key)
    except Exception:
        return 0


def _delete_landing_after_finalize(file_key: str) -> str | None:
    """
    Best-effort cleanup after the DB audit row is committed.

    A delete failure should not turn a loaded/quarantined file into a failed
    ingestion. Discovery skips finalized audit rows, so a reconciliation job can
    safely clean up any copied-but-not-deleted landing objects later.
    """
    try:
        delete_object(LANDING_BUCKET, file_key)
    except Exception as exc:
        return f"Landing delete failed after finalization: {exc}"
    return None


def _clean_string(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    return value


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
