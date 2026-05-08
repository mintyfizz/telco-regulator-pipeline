"""
SMS traffic domain generator.

Produces bronze.traffic_sms rows per (operator, period, region).

Calibrated against ARPCE 2024 anchors:
- 4.643 billion outgoing SMS nationally (declining 15.7% YoY)
- 98.81% on-net, 1.18% off-net, 0.01% international
- 54 million incoming SMS (national interconnection only)
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np

from telco_generator.constants.operators import (
    OperatorProfile,
    get_mobile_market_operators,
)
from telco_generator.constants.regions import get_population_weights
from telco_generator.constants.trajectories import TOTAL_SMS_TRAFFIC_OUTGOING
from telco_generator.utils.interpolation import interpolate_yearly
from telco_generator.utils.logging import get_logger
from telco_generator.utils.noise import lognormal_noise, seasonal_factor
from telco_generator.utils.time import ReportingPeriod

logger = get_logger(__name__)

# Destination shares from ARPCE 2024 report.
SMS_ONNET_SHARE = 0.9881
SMS_OFFNET_SHARE = 0.0118
SMS_INTERNATIONAL_OUTGOING_SHARE = 0.0001
SMS_INCOMING_NATIONAL_RATIO = 0.0118


@dataclass
class TrafficSmsRow:
    bronze_id: str
    source_submission_id: str
    operator_id: str
    report_period: str
    region_code: str
    service_segment: str
    sms_count_outgoing_onnet: int
    sms_count_outgoing_offnet: int
    sms_count_outgoing_international: int
    sms_count_incoming_national: int
    submitted_at: str
    _source_file: str
    _source_line: int
    _loaded_at: str
    _loaded_by_run_id: str
    _raw_payload: str


def _allocate_to_operators(
    national_total: int,
    operators: list[OperatorProfile],
) -> dict[str, int]:
    weights = {op.operator_id: op.mobile_subscribers_2024 for op in operators}
    total_weight = sum(weights.values())
    return {
        op_id: int(national_total * (w / total_weight))
        for op_id, w in weights.items()
    }


def _allocate_to_regions(
    operator_total: int,
    rng: np.random.Generator,
) -> dict[str, int]:
    weights = get_population_weights()
    return {
        region_code: int(operator_total * weight * lognormal_noise(rng, sigma=0.08))
        for region_code, weight in weights.items()
    }


def _make_row(
    operator_id: str,
    period: ReportingPeriod,
    region_code: str,
    onnet: int,
    offnet: int,
    intl: int,
    incoming: int,
    source_file: str,
    source_line: int,
    run_id: str,
) -> TrafficSmsRow:
    submission_id = f"SMS-{operator_id}-{period.period_str}-{region_code}"
    raw_payload = {
        "operator_id": operator_id,
        "report_period": period.period_str,
        "region_code": region_code,
        "service_segment": "mobile",
        "sms_count_outgoing_onnet": onnet,
        "sms_count_outgoing_offnet": offnet,
        "sms_count_outgoing_international": intl,
        "sms_count_incoming_national": incoming,
    }
    return TrafficSmsRow(
        bronze_id=str(uuid.uuid4()),
        source_submission_id=submission_id,
        operator_id=operator_id,
        report_period=period.period_str,
        region_code=region_code,
        service_segment="mobile",
        sms_count_outgoing_onnet=onnet,
        sms_count_outgoing_offnet=offnet,
        sms_count_outgoing_international=intl,
        sms_count_incoming_national=incoming,
        submitted_at=period.submission_timestamp().isoformat(),
        _source_file=source_file,
        _source_line=source_line,
        _loaded_at=datetime.now().isoformat(),
        _loaded_by_run_id=run_id,
        _raw_payload=json.dumps(raw_payload),
    )


def generate_traffic_sms_for_period(
    period: ReportingPeriod,
    rng: np.random.Generator,
    run_id: str,
    source_file: str = "synthetic_traffic_sms.csv",
) -> list[TrafficSmsRow]:
    rows: list[TrafficSmsRow] = []
    line_counter = 1

    national_annual = interpolate_yearly(
        TOTAL_SMS_TRAFFIC_OUTGOING, period.year, period.month
    )
    monthly_national = national_annual / 12 * seasonal_factor(period.month, amplitude=0.06)

    mobile_ops = get_mobile_market_operators()
    per_operator = _allocate_to_operators(int(monthly_national), mobile_ops)

    for operator in mobile_ops:
        op_id = operator.operator_id
        per_region = _allocate_to_regions(per_operator[op_id], rng)

        for region_code, region_total in per_region.items():
            if region_total < 100:
                continue

            onnet = int(region_total * SMS_ONNET_SHARE * lognormal_noise(rng, sigma=0.05))
            offnet = int(region_total * SMS_OFFNET_SHARE * lognormal_noise(rng, sigma=0.15))
            intl = int(
                region_total * SMS_INTERNATIONAL_OUTGOING_SHARE * lognormal_noise(rng, sigma=0.20)
            )
            incoming = int(
                region_total * SMS_INCOMING_NATIONAL_RATIO * lognormal_noise(rng, sigma=0.15)
            )

            rows.append(_make_row(
                op_id, period, region_code,
                onnet, offnet, intl, incoming,
                source_file, line_counter, run_id,
            ))
            line_counter += 1

    logger.info("generated_traffic_sms", period=period.period_str, rows=len(rows))
    return rows


def rows_to_records(rows: list[TrafficSmsRow]) -> list[dict]:
    return [asdict(row) for row in rows]
