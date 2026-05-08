"""Airflow DAG that ingests segmented measurement CSVs into bronze tables."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context
from lib.segment_domain_ingestion import (
    DOMAIN_CONFIGS,
    discover_segment_domain_files,
    finish_segment_domains_run,
    process_segment_domain_file,
    start_segment_domains_run,
)

DAG_ID = "bronze_segment_domains_ingestion"
DOMAINS = sorted(DOMAIN_CONFIGS)
BATCH_SIZE = 250


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


@dag(
    dag_id=DAG_ID,
    start_date=datetime(2024, 1, 1),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    tags=["bronze", "segmented", "ingestion"],
)
def bronze_segment_domains_ingestion_dag() -> None:
    """Load structurally valid traffic, QoS, and revenue submissions."""

    @task
    def start_run() -> str:
        context = get_current_context()
        dag_run = context.get("dag_run")
        run_type = str(getattr(dag_run, "run_type", "scheduled"))
        return start_segment_domains_run(DAG_ID, run_type=run_type)

    @task
    def discover_files(pipeline_run_id: str) -> list[dict[str, Any]]:
        file_keys = discover_segment_domain_files(DOMAINS)
        return [
            {"file_keys": batch, "pipeline_run_id": pipeline_run_id}
            for batch in _chunked(file_keys, BATCH_SIZE)
        ]

    @task
    def process_file_batch(file_keys: list[str], pipeline_run_id: str) -> list[dict[str, Any]]:
        return [
            process_segment_domain_file(file_key=file_key, run_id=pipeline_run_id)
            for file_key in file_keys
        ]

    @task
    def finish_run(
        pipeline_run_id: str,
        results: list[list[dict[str, Any]]] | None,
    ) -> dict[str, Any]:
        flattened = [
            result
            for batch_results in (results or [])
            for result in (batch_results or [])
        ]
        return finish_segment_domains_run(run_id=pipeline_run_id, results=flattened)

    pipeline_run_id = start_run()
    batches = discover_files(pipeline_run_id)
    results = process_file_batch.expand_kwargs(batches)
    finish_run(pipeline_run_id, results)


bronze_segment_domains_ingestion_dag()
