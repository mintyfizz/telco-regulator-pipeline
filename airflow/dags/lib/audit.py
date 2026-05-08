"""
Audit trail helpers for Airflow ingestion DAGs.

The helper functions match infra/postgres/init/02_audit_tables.sql. Every DAG
run gets one audit.pipeline_runs row, and every processed file gets one
audit.file_ingestions row linked to that run.
"""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from lib.postgres_helpers import execute_sql


def start_pipeline_run(dag_id: str, task_id: str, run_type: str = "scheduled") -> str:
    """Insert a pipeline_runs row with status='running'. Returns run_id UUID."""
    run_id = str(uuid.uuid4())
    sql = """
        INSERT INTO audit.pipeline_runs
            (run_id, dag_id, task_id, status, started_at, metadata)
        VALUES (%s, %s, %s, 'running', %s, %s::jsonb)
    """
    execute_sql(
        sql,
        (run_id, dag_id, task_id, datetime.now(UTC), json.dumps({"run_type": run_type})),
    )
    return run_id


def finish_pipeline_run(
    run_id: str,
    status: str,
    files_processed: int = 0,
    records_processed: int = 0,
    records_failed: int = 0,
    error_message: str | None = None,
) -> None:
    """
    Update pipeline_runs with final status and stats.

    status must be one of: success, failed, cancelled.
    """
    sql = """
        UPDATE audit.pipeline_runs
        SET status = %s,
            completed_at = %s,
            records_processed = %s,
            records_failed = %s,
            error_message = %s,
            metadata = metadata || %s::jsonb
        WHERE run_id = %s
    """
    execute_sql(
        sql,
        (
            status,
            datetime.now(UTC),
            records_processed,
            records_failed,
            error_message,
            json.dumps({"files_processed": files_processed}),
            run_id,
        ),
    )


def record_file_ingestion(
    run_id: str,
    source_file: str,
    source_bucket: str,
    data_domain: str,
    operator_id: str,
    status: str,
    file_size_bytes: int,
    rows_total: int = 0,
    rows_loaded: int = 0,
    rows_quarantined: int = 0,
    report_period: str | None = None,
    file_checksum_sha256: str | None = None,
    error_message: str | None = None,
    conn: Any | None = None,
) -> None:
    """Insert one row into audit.file_ingestions for a processed file."""
    sql = """
        INSERT INTO audit.file_ingestions
            (run_id, source_file, source_bucket, data_domain, operator_id,
             status, file_size_bytes, rows_total, rows_loaded, rows_quarantined,
             report_period, file_checksum_sha256, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    params = (
        run_id, source_file, source_bucket, data_domain, operator_id,
        status, file_size_bytes, rows_total, rows_loaded, rows_quarantined,
        report_period, file_checksum_sha256, error_message,
    )
    if conn is None:
        execute_sql(sql, params)
        return

    with conn.cursor() as cur:
        cur.execute(sql, params)


def file_already_loaded(source_file: str, source_bucket: str) -> bool:
    """Return True if this file has a successful ingestion record (idempotency guard)."""
    sql = """
        SELECT 1 FROM audit.file_ingestions
        WHERE source_file = %s AND source_bucket = %s AND status = 'loaded'
        LIMIT 1
    """
    return execute_sql(sql, (source_file, source_bucket), fetch_one=True) is not None


def loaded_files_for_bucket(source_bucket: str) -> set[str]:
    """Return all successfully loaded source_file keys for a bucket."""
    sql = """
        SELECT source_file FROM audit.file_ingestions
        WHERE source_bucket = %s AND status = 'loaded'
    """
    rows = execute_sql(sql, (source_bucket,), fetch_all=True) or []
    return {row[0] for row in rows}


def finalized_files_for_bucket(source_bucket: str) -> set[str]:
    """Return source_file keys that reached a terminal loaded/quarantined state."""
    sql = """
        SELECT source_file FROM audit.file_ingestions
        WHERE source_bucket = %s AND status IN ('loaded', 'quarantined')
    """
    rows = execute_sql(sql, (source_bucket,), fetch_all=True) or []
    return {row[0] for row in rows}
