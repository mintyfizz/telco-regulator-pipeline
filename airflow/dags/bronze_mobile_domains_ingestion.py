"""Airflow DAG that ingests remaining mobile domain CSVs into bronze tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
from airflow.utils.trigger_rule import TriggerRule

from lib.mobile_domain_ingestion import (
    DOMAIN_CONFIGS,
    discover_mobile_domain_files,
    finish_mobile_domains_run,
    process_mobile_domain_file,
    start_mobile_domains_run,
)

DAG_ID = "bronze_mobile_domains_ingestion"
DOMAINS = sorted(DOMAIN_CONFIGS)


@dag(
    dag_id=DAG_ID,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["bronze", "mobile", "ingestion"],
)
def bronze_mobile_domains_ingestion_dag() -> None:
    """Load structurally valid mobile traffic, QoS, and revenue submissions."""

    @task
    def start_run() -> str:
        context = get_current_context()
        dag_run = context.get("dag_run")
        run_type = str(getattr(dag_run, "run_type", "scheduled"))
        return start_mobile_domains_run(DAG_ID, run_type=run_type)

    @task
    def discover_files(pipeline_run_id: str) -> list[dict[str, str]]:
        return [
            {"file_key": file_key, "pipeline_run_id": pipeline_run_id}
            for file_key in discover_mobile_domain_files(DOMAINS)
        ]

    @task
    def process_file(file_key: str, pipeline_run_id: str) -> dict[str, Any]:
        return process_mobile_domain_file(file_key=file_key, run_id=pipeline_run_id)

    @task(trigger_rule=TriggerRule.ALL_DONE)
    def finish_run(
        pipeline_run_id: str,
        results: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        return finish_mobile_domains_run(run_id=pipeline_run_id, results=results)

    pipeline_run_id = start_run()
    files = discover_files(pipeline_run_id)
    results = process_file.expand_kwargs(files)
    finish_run(pipeline_run_id, results)


bronze_mobile_domains_ingestion_dag()
