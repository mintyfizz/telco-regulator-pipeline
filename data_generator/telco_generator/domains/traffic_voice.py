"""
Voice traffic domain generator.

Produces bronze.traffic_voice rows per (operator, period, region).

Calibrated against ARPCE 2024 anchors:
- 6.102 billion outgoing minutes nationally
- 86.2% on-net, 13.6% off-net, 0.2% international outgoing
- 846 million incoming minutes (98% national, 2% international)
- Largest two fictional operators dominate outgoing voice traffic.
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np

from telco_generator.constants.operators import (
    OperatorProfile,
    get_fixed_voice_operators,
    get_mobile_market_operators,
)
from telco_generator.constants.regions import get_population_weights
from telco_generator.constants.trajectories import TOTAL_VOICE_TRAFFIC_OUTGOING
from telco_generator.utils.interpolation import interpolate_yearly
from telco_generator.utils.logging import get_logger
from telco_generator.utils.noise import lognormal_noise, seasonal_factor
from telco_generator.utils.time import ReportingPeriod

logger = get_logger(__name__)

# Destination shares from ARPCE 2024 report.
ONNET_SHARE = 0.862
OFFNET_SHARE = 0.136
INTERNATIONAL_OUTGOING_SHARE = 0.002

# Incoming volume relative to outgoing.
INCOMING_NATIONAL_RATIO = 0.136  # roughly equal to off-net outgoing across duopoly
INCOMING_INTERNATIONAL_RATIO = 0.0026

# Fixed voice assumptions. Public calibration is mobile-first, so these are
# conservative synthetic anchors for a small fixed-line segment.
FIXED_MONTHLY_MINUTES_PER_SUBSCRIBER = 75
FIXED_LOCAL_SHARE = 0.62
FIXED_NATIONAL_SHARE = 0.32
FIXED_INTERNATIONAL_OUTGOING_SHARE = 0.06
FIXED_INCOMING_NATIONAL_RATIO = 0.28
FIXED_INCOMING_INTERNATIONAL_RATIO = 0.03


@dataclass
class TrafficVoiceRow:
    bronze_id: str
    source_submission_id: str
    operator_id: str
    report_period: str
    region_code: str
    service_segment: str
    voice_minutes_outgoing_onnet: int
    voice_minutes_outgoing_offnet: int
    voice_minutes_outgoing_international: int
    voice_minutes_incoming_national: int
    voice_minutes_incoming_international: int
    voice_minutes_fixed_local: int
    voice_minutes_fixed_national: int
    voice_minutes_fixed_international_outgoing: int
    voice_minutes_fixed_incoming_national: int
    voice_minutes_fixed_incoming_international: int
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
    """Allocate national voice total across mobile operators by 2024 share."""
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
    """Distribute operator voice traffic across regions by population share."""
    weights = get_population_weights()
    return {
        region_code: int(operator_total * weight * lognormal_noise(rng, sigma=0.08))
        for region_code, weight in weights.items()
    }


def _make_row(
    operator_id: str,
    period: ReportingPeriod,
    region_code: str,
    service_segment: str,
    onnet: int,
    offnet: int,
    intl_out: int,
    incoming_nat: int,
    incoming_intl: int,
    fixed_local: int,
    fixed_national: int,
    fixed_intl_out: int,
    fixed_in_nat: int,
    fixed_in_intl: int,
    source_file: str,
    source_line: int,
    run_id: str,
) -> TrafficVoiceRow:
    submission_id = f"VOI-{operator_id}-{period.period_str}-{region_code}"
    raw_payload = {
        "operator_id": operator_id,
        "report_period": period.period_str,
        "region_code": region_code,
        "service_segment": service_segment,
        "voice_minutes_outgoing_onnet": onnet,
        "voice_minutes_outgoing_offnet": offnet,
        "voice_minutes_outgoing_international": intl_out,
        "voice_minutes_incoming_national": incoming_nat,
        "voice_minutes_incoming_international": incoming_intl,
        "voice_minutes_fixed_local": fixed_local,
        "voice_minutes_fixed_national": fixed_national,
        "voice_minutes_fixed_international_outgoing": fixed_intl_out,
        "voice_minutes_fixed_incoming_national": fixed_in_nat,
        "voice_minutes_fixed_incoming_international": fixed_in_intl,
    }
    return TrafficVoiceRow(
        bronze_id=str(uuid.uuid4()),
        source_submission_id=submission_id,
        operator_id=operator_id,
        report_period=period.period_str,
        region_code=region_code,
        service_segment=service_segment,
        voice_minutes_outgoing_onnet=onnet,
        voice_minutes_outgoing_offnet=offnet,
        voice_minutes_outgoing_international=intl_out,
        voice_minutes_incoming_national=incoming_nat,
        voice_minutes_incoming_international=incoming_intl,
        voice_minutes_fixed_local=fixed_local,
        voice_minutes_fixed_national=fixed_national,
        voice_minutes_fixed_international_outgoing=fixed_intl_out,
        voice_minutes_fixed_incoming_national=fixed_in_nat,
        voice_minutes_fixed_incoming_international=fixed_in_intl,
        submitted_at=period.submission_timestamp().isoformat(),
        _source_file=source_file,
        _source_line=source_line,
        _loaded_at=datetime.now().isoformat(),
        _loaded_by_run_id=run_id,
        _raw_payload=json.dumps(raw_payload),
    )


def generate_traffic_voice_for_period(
    period: ReportingPeriod,
    rng: np.random.Generator,
    run_id: str,
    source_file: str = "synthetic_traffic_voice.csv",
) -> list[TrafficVoiceRow]:
    """Generate voice traffic rows for a single reporting period."""
    rows: list[TrafficVoiceRow] = []
    line_counter = 1

    # Annual total → monthly (with seasonal adjustment).
    national_annual = interpolate_yearly(
        TOTAL_VOICE_TRAFFIC_OUTGOING, period.year, period.month
    )
    monthly_national = national_annual / 12 * seasonal_factor(period.month, amplitude=0.04)

    mobile_ops = get_mobile_market_operators()
    per_operator = _allocate_to_operators(int(monthly_national), mobile_ops)

    for operator in mobile_ops:
        op_id = operator.operator_id
        op_total = per_operator[op_id]
        per_region = _allocate_to_regions(op_total, rng)

        for region_code, region_total in per_region.items():
            if region_total < 1000:
                continue

            onnet = int(region_total * ONNET_SHARE * lognormal_noise(rng, sigma=0.05))
            offnet = int(region_total * OFFNET_SHARE * lognormal_noise(rng, sigma=0.10))
            intl_out = int(
                region_total * INTERNATIONAL_OUTGOING_SHARE * lognormal_noise(rng, sigma=0.15)
            )
            incoming_nat = int(
                region_total * INCOMING_NATIONAL_RATIO * lognormal_noise(rng, sigma=0.10)
            )
            incoming_intl = int(
                region_total * INCOMING_INTERNATIONAL_RATIO * lognormal_noise(rng, sigma=0.20)
            )

            rows.append(_make_row(
                op_id, period, region_code,
                "mobile",
                onnet, offnet, intl_out, incoming_nat, incoming_intl,
                0, 0, 0, 0, 0,
                source_file, line_counter, run_id,
            ))
            line_counter += 1

    for operator in get_fixed_voice_operators():
        fixed_subscribers = int(
            operator.fixed_subscribers_2024
            * ((1 + operator.mobile_growth_rate_annual) ** (period.year - 2024))
        )
        monthly_total = (
            fixed_subscribers
            * FIXED_MONTHLY_MINUTES_PER_SUBSCRIBER
            * seasonal_factor(period.month, amplitude=0.03)
        )
        per_region = _allocate_to_regions(int(monthly_total), rng)

        for region_code, region_total in per_region.items():
            if region_total < 500:
                continue

            fixed_local = int(region_total * FIXED_LOCAL_SHARE * lognormal_noise(rng, sigma=0.06))
            fixed_national = int(
                region_total * FIXED_NATIONAL_SHARE * lognormal_noise(rng, sigma=0.08)
            )
            fixed_intl_out = int(
                region_total
                * FIXED_INTERNATIONAL_OUTGOING_SHARE
                * lognormal_noise(rng, sigma=0.15)
            )
            fixed_in_nat = int(
                region_total * FIXED_INCOMING_NATIONAL_RATIO * lognormal_noise(rng, sigma=0.10)
            )
            fixed_in_intl = int(
                region_total
                * FIXED_INCOMING_INTERNATIONAL_RATIO
                * lognormal_noise(rng, sigma=0.20)
            )

            rows.append(_make_row(
                operator.operator_id, period, region_code,
                "fixed_voice",
                0, 0, 0, 0, 0,
                fixed_local, fixed_national, fixed_intl_out, fixed_in_nat, fixed_in_intl,
                source_file, line_counter, run_id,
            ))
            line_counter += 1

    logger.info("generated_traffic_voice", period=period.period_str, rows=len(rows))
    return rows


def rows_to_records(rows: list[TrafficVoiceRow]) -> list[dict]:
    return [asdict(row) for row in rows]
