"""Monthly reporting pipeline: generate, upload, ingest, and validate one period."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException, AirflowSkipException
from airflow.operators.python import get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from telco_generator.config import GeneratorConfig
from telco_generator.orchestrator import run_generator
from telco_generator.uploaders.minio_client import MinioConfig
from telco_generator.uploaders.minio_uploader import upload_all
from telco_generator.utils.time import parse_reporting_period

DAG_ID = "monthly_reporting_pipeline"
WAREHOUSE_CONN_ID = "telco_warehouse"
MINIO_ENDPOINT = "http://minio:9000"
MINIO_ACCESS_KEY = "minio_admin"
MINIO_SECRET_KEY = "changeme_local_only"
OUTPUT_BASE_DIR = Path("/tmp/telco_monthly_reporting")


def _period_from_logical_date(logical_date: Any) -> str:
    """Return the reporting period that closed before this DAG run date."""
    previous_month = logical_date.subtract(months=1)
    return previous_month.format("YYYY-MM")


def _seed_for_period(period: str) -> int:
    """Deterministic default seed: 2025-03 -> 202503."""
    return int(period.replace("-", ""))


@dag(
    dag_id=DAG_ID,
    start_date=datetime(2020, 2, 5),
    schedule="0 3 5 * *",
    catchup=True,
    max_active_runs=1,
    tags=["monthly", "generation", "bronze", "silver"],
    params={
        "anomaly_rate": 0.02,
        "seed": None,
    },
)
def monthly_reporting_pipeline_dag() -> None:
    """
    Simulate the monthly regulator reporting cycle.

    Scheduled runs execute on the 5th of each month and process the previous
    closed reporting period. Backfill/catchup therefore fills missing months
    from 2020-01 onward. Existing fully loaded periods are skipped to avoid
    duplicate bronze rows.
    """

    @task
    def resolve_reporting_period() -> str:
        context = get_current_context()
        dag_run = context.get("dag_run")
        conf = getattr(dag_run, "conf", None) or {}
        period = conf.get("period") or _period_from_logical_date(context["logical_date"])
        parse_reporting_period(period)
        return period

    @task
    def inspect_period(period: str) -> dict[str, Any]:
        sql = """
            SELECT 'subscribers' AS domain, COUNT(*)
            FROM bronze.subscribers
            WHERE report_period = %s
            UNION ALL
            SELECT 'traffic_voice', COUNT(*)
            FROM bronze.traffic_voice
            WHERE report_period = %s
            UNION ALL
            SELECT 'traffic_sms', COUNT(*)
            FROM bronze.traffic_sms
            WHERE report_period = %s
            UNION ALL
            SELECT 'traffic_internet', COUNT(*)
            FROM bronze.traffic_internet
            WHERE report_period = %s
            UNION ALL
            SELECT 'qos', COUNT(*)
            FROM bronze.qos
            WHERE report_period = %s
            UNION ALL
            SELECT 'revenue', COUNT(*)
            FROM bronze.revenue
            WHERE report_period = %s
        """
        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)
        rows = hook.get_records(sql, parameters=(period, period, period, period, period, period))
        counts = {domain: int(count) for domain, count in rows}
        loaded_domains = [domain for domain, count in counts.items() if count > 0]

        if len(loaded_domains) == 6:
            status = "loaded"
        elif loaded_domains:
            status = "partial"
        else:
            status = "empty"

        return {
            "period": period,
            "status": status,
            "counts": counts,
            "loaded_domains": loaded_domains,
        }

    @task
    def generate_month(period: str, period_status: dict[str, Any]) -> dict[str, Any]:
        status = period_status["status"]
        if status == "loaded":
            return {
                "period": period,
                "generated": False,
                "reason": "period already fully loaded in bronze",
            }
        if status == "partial":
            raise AirflowException(
                f"Refusing to auto-generate {period}: bronze already has partial data "
                f"for domains {period_status['loaded_domains']}. Clean up or handle manually."
            )

        context = get_current_context()
        params = context.get("params", {})
        anomaly_rate = float(params.get("anomaly_rate") or 0.0)
        seed_param = params.get("seed")
        seed = int(seed_param) if seed_param is not None else _seed_for_period(period)

        output_dir = OUTPUT_BASE_DIR / period
        shutil.rmtree(output_dir, ignore_errors=True)

        totals = run_generator(
            GeneratorConfig(
                period=period,
                output_dir=output_dir,
                random_seed=seed,
                anomaly_rate=anomaly_rate,
            )
        )

        return {
            "period": period,
            "generated": True,
            "output_dir": str(output_dir),
            "seed": seed,
            "anomaly_rate": anomaly_rate,
            "totals": totals,
        }

    @task
    def upload_month(generation_result: dict[str, Any]) -> dict[str, Any]:
        if not generation_result.get("generated"):
            return {
                "period": generation_result["period"],
                "uploaded": False,
                "reason": generation_result.get("reason", "generation skipped"),
            }

        stats = upload_all(
            output_dir=Path(generation_result["output_dir"]),
            minio_config=MinioConfig(
                endpoint_url=MINIO_ENDPOINT,
                access_key=MINIO_ACCESS_KEY,
                secret_key=MINIO_SECRET_KEY,
            ),
            skip_existing=True,
        )

        if stats.files_failed:
            raise AirflowException(
                f"{stats.files_failed} generated file(s) failed to upload for "
                f"{generation_result['period']}"
            )

        return {
            "period": generation_result["period"],
            "uploaded": True,
            "files_uploaded": stats.files_uploaded,
            "files_skipped": stats.files_skipped,
            "bytes_uploaded": stats.bytes_uploaded,
        }

    @task
    def require_month_upload(upload_result: dict[str, Any]) -> dict[str, Any]:
        if not upload_result.get("uploaded"):
            raise AirflowSkipException(
                f"Skipping ingestion for {upload_result['period']}: "
                f"{upload_result.get('reason', 'nothing uploaded')}"
            )
        return upload_result

    @task
    def run_silver_validations() -> dict[str, Any]:
        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)
        rows = hook.get_records("SELECT * FROM silver.run_all_validations();")
        event_rows = hook.get_records(
            "SELECT silver.capture_suspicious_anomaly_events();"
        )
        event_count = int(event_rows[0][0]) if event_rows else 0
        return {
            "validation_results": [
            {
                "domain": domain,
                "rows_processed": int(rows_processed),
                "rows_validated": int(rows_validated),
                "rows_rejected": int(rows_rejected),
            }
            for domain, rows_processed, rows_validated, rows_rejected in rows
            ],
            "events_captured": event_count,
        }

    period = resolve_reporting_period()
    period_status = inspect_period(period)
    generation_result = generate_month(period, period_status)
    upload_result = upload_month(generation_result)
    ready_for_ingestion = require_month_upload(upload_result)

    run_subscribers_ingestion = TriggerDagRunOperator(
        task_id="run_subscribers_ingestion",
        trigger_dag_id="bronze_subscribers_ingestion",
        trigger_run_id=(
            "monthly_subscribers__"
            "{{ ti.xcom_pull(task_ids='resolve_reporting_period') }}__"
            "{{ ts_nodash }}"
        ),
        wait_for_completion=True,
        reset_dag_run=True,
        poke_interval=10,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    run_segment_ingestion = TriggerDagRunOperator(
        task_id="run_segment_ingestion",
        trigger_dag_id="bronze_segment_domains_ingestion",
        trigger_run_id=(
            "monthly_segments__"
            "{{ ti.xcom_pull(task_ids='resolve_reporting_period') }}__"
            "{{ ts_nodash }}"
        ),
        wait_for_completion=True,
        reset_dag_run=True,
        poke_interval=10,
        allowed_states=["success"],
        failed_states=["failed"],
    )

    silver_results = run_silver_validations()

    ready_for_ingestion >> run_subscribers_ingestion >> run_segment_ingestion >> silver_results


monthly_reporting_pipeline_dag()
