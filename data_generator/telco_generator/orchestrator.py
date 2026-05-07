"""
Top-level orchestration: generate all domains for a configured date range.

Writes CSVs to the configured output directory, organized as:
output/<domain>/<year>/<month>.csv
"""

import csv
import uuid
from pathlib import Path

import numpy as np

from telco_generator.config import GeneratorConfig
from telco_generator.domains import (
    qos,
    revenue,
    subscribers,
    traffic_internet,
    traffic_sms,
    traffic_voice,
)
from telco_generator.utils.logging import get_logger
from telco_generator.utils.time import ReportingPeriod, generate_periods

logger = get_logger(__name__)


def _write_csv(records: list[dict], output_path: Path) -> None:
    """Write a list of dicts to CSV with header row."""
    if not records:
        logger.warning("no_records_to_write", path=str(output_path))
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(records[0].keys())

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    logger.info("wrote_csv", path=str(output_path), rows=len(records))


def _output_path(base: Path, domain: str, period: ReportingPeriod) -> Path:
    return base / domain / str(period.year) / f"{period.period_str}.csv"


def run_generator(config: GeneratorConfig) -> dict[str, int]:
    """
    Execute the full generation run.

    Returns a dict mapping domain name to total rows written.
    """
    rng = np.random.default_rng(seed=config.random_seed)
    run_id = str(uuid.uuid4())
    periods = generate_periods(config.start_year, config.end_year)

    logger.info(
        "starting_generation",
        run_id=run_id,
        periods=len(periods),
        domains=config.domains,
        output_dir=str(config.output_dir),
    )

    totals: dict[str, int] = {d: 0 for d in config.domains}

    for period in periods:
        logger.info("processing_period", period=period.period_str)

        if "subscribers" in config.domains:
            rows = subscribers.generate_subscribers_for_period(period, rng, run_id)
            _write_csv(
                subscribers.rows_to_records(rows),
                _output_path(config.output_dir, "subscribers", period),
            )
            totals["subscribers"] += len(rows)

        if "traffic_voice" in config.domains:
            rows = traffic_voice.generate_traffic_voice_for_period(period, rng, run_id)
            _write_csv(
                traffic_voice.rows_to_records(rows),
                _output_path(config.output_dir, "traffic_voice", period),
            )
            totals["traffic_voice"] += len(rows)

        if "traffic_sms" in config.domains:
            rows = traffic_sms.generate_traffic_sms_for_period(period, rng, run_id)
            _write_csv(
                traffic_sms.rows_to_records(rows),
                _output_path(config.output_dir, "traffic_sms", period),
            )
            totals["traffic_sms"] += len(rows)

        if "traffic_internet" in config.domains:
            rows = traffic_internet.generate_traffic_internet_for_period(period, rng, run_id)
            _write_csv(
                traffic_internet.rows_to_records(rows),
                _output_path(config.output_dir, "traffic_internet", period),
            )
            totals["traffic_internet"] += len(rows)

        if "qos" in config.domains:
            rows = qos.generate_qos_for_period(
                period, rng, run_id,
                qos_gaming_rate=config.qos_gaming_rate,
            )
            _write_csv(
                qos.rows_to_records(rows),
                _output_path(config.output_dir, "qos", period),
            )
            totals["qos"] += len(rows)

        if "revenue" in config.domains:
            rows = revenue.generate_revenue_for_period(period, rng, run_id)
            _write_csv(
                revenue.rows_to_records(rows),
                _output_path(config.output_dir, "revenue", period),
            )
            totals["revenue"] += len(rows)

    logger.info("generation_complete", totals=totals)
    return totals
