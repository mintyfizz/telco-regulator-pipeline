"""
Internet traffic domain generator.

Produces bronze.traffic_internet rows per (operator, period, region).

Calibrated against ARPCE 2024 anchors:
- 90.904 billion MB total nationally
- 75.2% 4G, 24.4% 3G, 0.3% 2G
- Largest two fictional operators dominate mobile internet traffic.
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np

from telco_generator.constants.operators import (
    OperatorProfile,
    get_mobile_internet_market_operators,
)
from telco_generator.constants.regions import get_population_weights
from telco_generator.constants.trajectories import (
    INTERNET_TRAFFIC_SHARES,
    TOTAL_INTERNET_TRAFFIC_MB,
)
from telco_generator.utils.interpolation import (
    interpolate_yearly,
    interpolate_yearly_dict,
)
from telco_generator.utils.logging import get_logger
from telco_generator.utils.noise import lognormal_noise, seasonal_factor
from telco_generator.utils.time import ReportingPeriod

logger = get_logger(__name__)


@dataclass
class TrafficInternetRow:
    bronze_id: str
    source_submission_id: str
    operator_id: str
    report_period: str
    region_code: str
    service_segment: str
    data_consumed_mb_2g: float
    data_consumed_mb_3g: float
    data_consumed_mb_4g: float
    data_consumed_mb_5g: float | None
    submitted_at: str
    _source_file: str
    _source_line: int
    _loaded_at: str
    _loaded_by_run_id: str
    _raw_payload: str


def _allocate_to_operators(
    national_total: float,
    operators: list[OperatorProfile],
) -> dict[str, float]:
    """Internet traffic allocation uses internet subscriber counts as weights."""
    weights = {op.operator_id: op.mobile_internet_subscribers_2024 for op in operators}
    total_weight = sum(weights.values())
    return {
        op_id: national_total * (w / total_weight)
        for op_id, w in weights.items()
    }


def _allocate_to_regions(
    operator_total: float,
    rng: np.random.Generator,
) -> dict[str, float]:
    weights = get_population_weights()
    return {
        region_code: operator_total * weight * lognormal_noise(rng, sigma=0.10)
        for region_code, weight in weights.items()
    }


def _make_row(
    operator_id: str,
    period: ReportingPeriod,
    region_code: str,
    mb_2g: float,
    mb_3g: float,
    mb_4g: float,
    source_file: str,
    source_line: int,
    run_id: str,
) -> TrafficInternetRow:
    submission_id = f"NET-{operator_id}-{period.period_str}-{region_code}"
    raw_payload = {
        "operator_id": operator_id,
        "report_period": period.period_str,
        "region_code": region_code,
        "service_segment": "mobile",
        "data_consumed_mb_2g": mb_2g,
        "data_consumed_mb_3g": mb_3g,
        "data_consumed_mb_4g": mb_4g,
    }
    return TrafficInternetRow(
        bronze_id=str(uuid.uuid4()),
        source_submission_id=submission_id,
        operator_id=operator_id,
        report_period=period.period_str,
        region_code=region_code,
        service_segment="mobile",
        data_consumed_mb_2g=round(mb_2g, 3),
        data_consumed_mb_3g=round(mb_3g, 3),
        data_consumed_mb_4g=round(mb_4g, 3),
        data_consumed_mb_5g=None,  # 5G not yet deployed in Congo
        submitted_at=period.submission_timestamp().isoformat(),
        _source_file=source_file,
        _source_line=source_line,
        _loaded_at=datetime.now().isoformat(),
        _loaded_by_run_id=run_id,
        _raw_payload=json.dumps(raw_payload),
    )


def generate_traffic_internet_for_period(
    period: ReportingPeriod,
    rng: np.random.Generator,
    run_id: str,
    source_file: str = "synthetic_traffic_internet.csv",
) -> list[TrafficInternetRow]:
    rows: list[TrafficInternetRow] = []
    line_counter = 1

    national_annual = interpolate_yearly(
        TOTAL_INTERNET_TRAFFIC_MB, period.year, period.month
    )
    monthly_national = national_annual / 12 * seasonal_factor(period.month, amplitude=0.05)

    share_2g = interpolate_yearly_dict(INTERNET_TRAFFIC_SHARES, period.year, period.month, "2G")
    share_3g = interpolate_yearly_dict(INTERNET_TRAFFIC_SHARES, period.year, period.month, "3G")
    share_4g = interpolate_yearly_dict(INTERNET_TRAFFIC_SHARES, period.year, period.month, "4G")

    internet_ops = get_mobile_internet_market_operators()
    per_operator = _allocate_to_operators(monthly_national, internet_ops)

    for operator in internet_ops:
        op_id = operator.operator_id
        per_region = _allocate_to_regions(per_operator[op_id], rng)

        for region_code, region_total in per_region.items():
            if region_total < 1000:
                continue

            mb_2g = region_total * share_2g * lognormal_noise(rng, sigma=0.15)
            mb_3g = region_total * share_3g * lognormal_noise(rng, sigma=0.08)
            mb_4g = region_total * share_4g * lognormal_noise(rng, sigma=0.06)

            rows.append(_make_row(
                op_id, period, region_code,
                mb_2g, mb_3g, mb_4g,
                source_file, line_counter, run_id,
            ))
            line_counter += 1

    logger.info("generated_traffic_internet", period=period.period_str, rows=len(rows))
    return rows


def rows_to_records(rows: list[TrafficInternetRow]) -> list[dict]:
    return [asdict(row) for row in rows]
