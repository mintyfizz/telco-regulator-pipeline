"""Monthly reporting pipeline: generate, upload, ingest, and validate one period."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from airflow.decorators import dag, task
from airflow.exceptions import AirflowException, AirflowSkipException
from airflow.hooks.base import BaseHook
from airflow.operators.python import get_current_context
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from telco_generator.config import GeneratorConfig
from telco_generator.orchestrator import run_generator
from telco_generator.pipeline_runtime import classify_period_status
from telco_generator.uploaders.minio_client import MinioConfig
from telco_generator.uploaders.minio_uploader import upload_all
from telco_generator.utils.time import parse_reporting_period

DAG_ID = "monthly_reporting_pipeline"
WAREHOUSE_CONN_ID = "telco_warehouse"
MINIO_CONN_ID = "telco_minio"
OUTPUT_BASE_DIR = Path("/tmp/telco_monthly_reporting")


def _period_from_logical_date(logical_date: Any) -> str:
    """Return the reporting period that closed before this DAG run date."""
    previous_month = logical_date.subtract(months=1)
    return previous_month.format("YYYY-MM")


def _seed_for_period(period: str) -> int:
    """Deterministic default seed: 2025-03 -> 202503."""
    return int(period.replace("-", ""))


def _minio_config_from_connection() -> MinioConfig:
    """Resolve MinIO settings from the Airflow telco_minio connection."""
    conn = BaseHook.get_connection(MINIO_CONN_ID)
    extra = conn.extra_dejson
    return MinioConfig(
        endpoint_url=str(extra.get("endpoint_url") or "http://minio:9000"),
        access_key=conn.login,
        secret_key=conn.password,
        region_name=str(extra.get("region_name") or "us-east-1"),
    )


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
            SELECT domain, row_count FROM (
                SELECT 'subscribers' AS domain, COUNT(*)::BIGINT AS row_count
                FROM bronze.subscribers WHERE report_period = %s
                UNION ALL
                SELECT 'traffic_voice', COUNT(*)::BIGINT
                FROM bronze.traffic_voice WHERE report_period = %s
                UNION ALL
                SELECT 'traffic_sms', COUNT(*)::BIGINT
                FROM bronze.traffic_sms WHERE report_period = %s
                UNION ALL
                SELECT 'traffic_internet', COUNT(*)::BIGINT
                FROM bronze.traffic_internet WHERE report_period = %s
                UNION ALL
                SELECT 'qos', COUNT(*)::BIGINT
                FROM bronze.qos WHERE report_period = %s
                UNION ALL
                SELECT 'revenue', COUNT(*)::BIGINT
                FROM bronze.revenue WHERE report_period = %s
            ) t
            ORDER BY domain
        """
        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)
        rows = hook.get_records(sql, parameters=(period, period, period, period, period, period))
        counts = {domain: int(count) for domain, count in rows}
        loaded_domains = [domain for domain, count in counts.items() if count > 0]
        status = classify_period_status(counts)

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
            minio_config=_minio_config_from_connection(),
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
    def run_silver_validations(period: str) -> dict[str, Any]:
        hook = PostgresHook(postgres_conn_id=WAREHOUSE_CONN_ID)
        validation_started_at = datetime.now(UTC)

        min_loaded_at_rows = hook.get_records(
            """
            SELECT MIN(loaded_at) FROM (
                SELECT MIN(_loaded_at) AS loaded_at FROM bronze.subscribers WHERE report_period = %s
                UNION ALL
                SELECT MIN(_loaded_at) FROM bronze.traffic_voice WHERE report_period = %s
                UNION ALL
                SELECT MIN(_loaded_at) FROM bronze.traffic_sms WHERE report_period = %s
                UNION ALL
                SELECT MIN(_loaded_at) FROM bronze.traffic_internet WHERE report_period = %s
                UNION ALL
                SELECT MIN(_loaded_at) FROM bronze.qos WHERE report_period = %s
                UNION ALL
                SELECT MIN(_loaded_at) FROM bronze.revenue WHERE report_period = %s
            ) t
            """,
            parameters=(period, period, period, period, period, period),
        )
        loaded_after = min_loaded_at_rows[0][0] if min_loaded_at_rows else None

        rows = hook.get_records(
            "SELECT * FROM silver.run_all_validations(%s, %s);",
            parameters=(None, loaded_after),
        )
        event_rows = hook.get_records(
            "SELECT silver.capture_suspicious_anomaly_events(%s, %s);",
            parameters=(None, loaded_after),
        )
        event_count = int(event_rows[0][0]) if event_rows else 0

        bronze_rows = hook.get_records(
            """
            SELECT domain, row_count FROM (
                SELECT 'subscribers' AS domain, COUNT(*)::BIGINT AS row_count
                FROM bronze.subscribers
                WHERE report_period = %s
                UNION ALL
                SELECT 'traffic_voice', COUNT(*)::BIGINT
                FROM bronze.traffic_voice
                WHERE report_period = %s
                UNION ALL
                SELECT 'traffic_sms', COUNT(*)::BIGINT
                FROM bronze.traffic_sms
                WHERE report_period = %s
                UNION ALL
                SELECT 'traffic_internet', COUNT(*)::BIGINT
                FROM bronze.traffic_internet
                WHERE report_period = %s
                UNION ALL
                SELECT 'qos', COUNT(*)::BIGINT
                FROM bronze.qos
                WHERE report_period = %s
                UNION ALL
                SELECT 'revenue', COUNT(*)::BIGINT
                FROM bronze.revenue
                WHERE report_period = %s
            ) t
            ORDER BY domain
            """,
            parameters=(period, period, period, period, period, period),
        )

        rejection_rows = hook.get_records(
            """
            SELECT domain, rejected_count FROM (
                SELECT 'subscribers' AS domain, COUNT(*)::BIGINT AS rejected_count
                FROM silver.subscribers_rejections r
                JOIN bronze.subscribers b ON b.bronze_id = r.bronze_id
                WHERE b.report_period = %s
                UNION ALL
                SELECT 'traffic_voice', COUNT(*)::BIGINT
                FROM silver.traffic_voice_rejections r
                JOIN bronze.traffic_voice b ON b.bronze_id = r.bronze_id
                WHERE b.report_period = %s
                UNION ALL
                SELECT 'traffic_sms', COUNT(*)::BIGINT
                FROM silver.traffic_sms_rejections r
                JOIN bronze.traffic_sms b ON b.bronze_id = r.bronze_id
                WHERE b.report_period = %s
                UNION ALL
                SELECT 'traffic_internet', COUNT(*)::BIGINT
                FROM silver.traffic_internet_rejections r
                JOIN bronze.traffic_internet b ON b.bronze_id = r.bronze_id
                WHERE b.report_period = %s
                UNION ALL
                SELECT 'qos', COUNT(*)::BIGINT
                FROM silver.qos_rejections r
                JOIN bronze.qos b ON b.bronze_id = r.bronze_id
                WHERE b.report_period = %s
                UNION ALL
                SELECT 'revenue', COUNT(*)::BIGINT
                FROM silver.revenue_rejections r
                JOIN bronze.revenue b ON b.bronze_id = r.bronze_id
                WHERE b.report_period = %s
            ) t
            ORDER BY domain
            """,
            parameters=(period, period, period, period, period, period),
        )

        alerts = hook.get_records(
            (
                "SELECT alert_code, severity, domain, report_period, "
                "event_count, threshold_value "
                "FROM silver.evaluate_quality_alerts(%s);"
            ),
            parameters=(period,),
        )

        return {
            "period": period,
            "validation_window_start": loaded_after.isoformat() if loaded_after else None,
            "validation_started_at": validation_started_at.isoformat(),
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
            "bronze_rows_by_domain": {domain: int(count) for domain, count in bronze_rows},
            "rejections_by_domain": {domain: int(count) for domain, count in rejection_rows},
            "alerts": [
                {
                    "alert_code": alert_code,
                    "severity": severity,
                    "domain": domain,
                    "report_period": report_period,
                    "event_count": int(event_count),
                    "threshold_value": int(threshold_value),
                }
                for (
                    alert_code,
                    severity,
                    domain,
                    report_period,
                    event_count,
                    threshold_value,
                ) in alerts
            ],
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

    silver_results = run_silver_validations(period)

    ready_for_ingestion >> run_subscribers_ingestion >> run_segment_ingestion >> silver_results


monthly_reporting_pipeline_dag()
