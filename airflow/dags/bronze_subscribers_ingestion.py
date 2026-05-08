"""Airflow DAG that ingests mobile subscriber CSVs into bronze.subscribers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
from airflow.utils.trigger_rule import TriggerRule

from lib.subscribers_ingestion import (
    discover_subscriber_files,
    finish_subscribers_run,
    process_subscriber_file,
    start_subscribers_run,
)

DAG_ID = "bronze_subscribers_ingestion"


@dag(
    dag_id=DAG_ID,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["bronze", "subscribers", "ingestion"],
)
def bronze_subscribers_ingestion_dag() -> None:
    """Load structurally valid mobile subscriber submissions into bronze."""

    @task
    def start_run() -> str:
        context = get_current_context()
        dag_run = context.get("dag_run")
        run_type = str(getattr(dag_run, "run_type", "scheduled"))
        return start_subscribers_run(DAG_ID, run_type=run_type)

    @task
    def discover_files(pipeline_run_id: str) -> list[dict[str, str]]:
        return [
            {"file_key": file_key, "pipeline_run_id": pipeline_run_id}
            for file_key in discover_subscriber_files()
        ]

    @task
    def process_file(file_key: str, pipeline_run_id: str) -> dict[str, Any]:
        return process_subscriber_file(file_key=file_key, run_id=pipeline_run_id)

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def finish_run(
        pipeline_run_id: str,
        results: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        return finish_subscribers_run(run_id=pipeline_run_id, results=results)

    pipeline_run_id = start_run()
    files = discover_files(pipeline_run_id)
    results = process_file.expand_kwargs(files)
    finish_run(pipeline_run_id, results)


bronze_subscribers_ingestion_dag()
