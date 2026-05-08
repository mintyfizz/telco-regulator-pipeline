"""
Subscribers domain generator.

Produces bronze.subscribers rows per (operator, period, region, service_category,
payment_type, technology_generation) combination.

Calibrated against ARPCE 2024 anchors:
- 6.050M mobile telephony subscribers nationally
- 3.757M mobile internet subscribers nationally
- 99% prepaid share
- Internet tech mix: 24% 2G, 31% 3G, 45% 4G
- Concentrated in Brazzaville (~35%) and Pointe-Noire (~23%)
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np

from telco_generator.constants.operators import (
    OperatorProfile,
    get_fixed_broadband_operators,
    get_fixed_voice_operators,
    get_mobile_internet_market_operators,
    get_mobile_market_operators,
)
from telco_generator.constants.regions import get_population_weights
from telco_generator.constants.trajectories import (
    INTERNET_TECH_SHARES,
    MOBILE_INTERNET_SUBSCRIBERS_NATIONAL,
    MOBILE_TELEPHONY_SUBSCRIBERS_NATIONAL,
)
from telco_generator.utils.interpolation import (
    interpolate_yearly,
    interpolate_yearly_dict,
)
from telco_generator.utils.logging import get_logger
from telco_generator.utils.noise import lognormal_noise, seasonal_factor
from telco_generator.utils.time import ReportingPeriod

logger = get_logger(__name__)

# Constants for subscriber decomposition.
PREPAID_SHARE = 0.99
POSTPAID_SHARE = 0.01
ACTIVE_30D_SHARE = 0.78  # 78% of total subscribers active in 30 days
MONTHLY_ACTIVATION_RATE = 0.04  # 4% gross adds per month
MONTHLY_CHURN_RATE = 0.03  # 3% gross churn per month
ARPU_TELEPHONY_BASE_2024 = 1_636  # FCFA per month
ARPU_INTERNET_4G_BASE_2024 = 2_482
ARPU_INTERNET_3G_BASE_2024 = 1_163
ARPU_INTERNET_2G_BASE_2024 = 21
ARPU_FIXED_VOICE_BASE_2024 = 7_500
ARPU_FIXED_BROADBAND_BASE_2024 = 18_000


@dataclass
class SubscriberRow:
    """A single bronze.subscribers row."""

    bronze_id: str
    source_submission_id: str
    operator_id: str
    report_period: str
    region_code: str
    service_segment: str
    service_category: str
    payment_type: str
    technology_generation: str | None
    total_subscribers: int
    active_subscribers_30d: int
    new_activations: int
    churn_count: int
    arpu_xaf: float
    submitted_at: str
    _source_file: str
    _source_line: int
    _loaded_at: str
    _loaded_by_run_id: str
    _raw_payload: str  # JSON-encoded


def _allocate_to_operators(
    national_total: int,
    operators: list[OperatorProfile],
    market_share_attr: str,
) -> dict[str, int]:
    """Allocate a national total across operators by their 2024 market share."""
    weights = {op.operator_id: getattr(op, market_share_attr) for op in operators}
    total_weight = sum(weights.values())
    if total_weight == 0:
        return {op_id: 0 for op_id in weights}
    return {
        op_id: int(national_total * (w / total_weight))
        for op_id, w in weights.items()
    }


def _allocate_to_regions(
    operator_total: int,
    rng: np.random.Generator,
) -> dict[str, int]:
    """Distribute an operator's total across regions, weighted by population."""
    weights = get_population_weights()
    allocated = {}
    for region_code, weight in weights.items():
        # Add 5% noise to regional weights so distribution isn't perfectly proportional.
        noisy_weight = weight * lognormal_noise(rng, sigma=0.08)
        allocated[region_code] = int(operator_total * noisy_weight)
    return allocated


def _arpu_for_segment(
    service_category: str,
    technology_generation: str | None,
    period: ReportingPeriod,
    operator: OperatorProfile,
    rng: np.random.Generator,
) -> float:
    """Compute ARPU for a specific segment."""
    if service_category == "mobile_telephony":
        base = ARPU_TELEPHONY_BASE_2024
    elif service_category == "mobile_internet":
        if technology_generation == "4G":
            base = ARPU_INTERNET_4G_BASE_2024
        elif technology_generation == "3G":
            base = ARPU_INTERNET_3G_BASE_2024
        else:
            base = ARPU_INTERNET_2G_BASE_2024
    elif service_category == "fixed_voice":
        base = ARPU_FIXED_VOICE_BASE_2024
    elif service_category == "fixed_broadband":
        base = ARPU_FIXED_BROADBAND_BASE_2024
    else:
        base = ARPU_TELEPHONY_BASE_2024

    # ARPU has been declining over time — apply a small annual decline.
    years_from_2024 = 2024 - period.year
    decline_factor = (1 - 0.02) ** years_from_2024  # 2% annual decline
    base = base * decline_factor

    # Operator-specific premium factor.
    base = base * operator.arpu_premium_factor

    # Add lognormal noise.
    return round(base * lognormal_noise(rng, sigma=0.06), 2)


def _make_row(
    operator_id: str,
    period: ReportingPeriod,
    region_code: str,
    service_segment: str,
    service_category: str,
    payment_type: str,
    technology_generation: str | None,
    total_subs: int,
    arpu: float,
    rng: np.random.Generator,
    source_file: str,
    source_line: int,
    run_id: str,
) -> SubscriberRow:
    """Construct a single subscriber row with all fields populated."""
    active_30d = int(total_subs * ACTIVE_30D_SHARE * lognormal_noise(rng, sigma=0.04))
    activations = int(total_subs * MONTHLY_ACTIVATION_RATE * lognormal_noise(rng, sigma=0.10))
    churn = int(total_subs * MONTHLY_CHURN_RATE * lognormal_noise(rng, sigma=0.10))

    submission_id = (
        f"SUB-{operator_id}-{period.period_str}-"
        f"{region_code}-{service_category[:3].upper()}"
    )

    raw_payload = {
        "operator_id": operator_id,
        "report_period": period.period_str,
        "region_code": region_code,
        "service_segment": service_segment,
        "service_category": service_category,
        "payment_type": payment_type,
        "technology_generation": technology_generation,
        "total_subscribers": total_subs,
        "active_subscribers_30d": active_30d,
        "new_activations": activations,
        "churn_count": churn,
        "arpu_xaf": arpu,
    }

    return SubscriberRow(
        bronze_id=str(uuid.uuid4()),
        source_submission_id=submission_id,
        operator_id=operator_id,
        report_period=period.period_str,
        region_code=region_code,
        service_segment=service_segment,
        service_category=service_category,
        payment_type=payment_type,
        technology_generation=technology_generation,
        total_subscribers=total_subs,
        active_subscribers_30d=min(active_30d, total_subs),
        new_activations=activations,
        churn_count=churn,
        arpu_xaf=arpu,
        submitted_at=period.submission_timestamp().isoformat(),
        _source_file=source_file,
        _source_line=source_line,
        _loaded_at=datetime.now().isoformat(),
        _loaded_by_run_id=run_id,
        _raw_payload=json.dumps(raw_payload),
    )


def generate_subscribers_for_period(
    period: ReportingPeriod,
    rng: np.random.Generator,
    run_id: str,
    source_file: str = "synthetic_subscribers.csv",
) -> list[SubscriberRow]:
    """
    Generate all subscriber rows for a single reporting period.

    Returns rows across all (operator, region, service_category, payment_type,
    technology_generation) combinations relevant for that period.
    """
    rows: list[SubscriberRow] = []
    line_counter = 1

    # National totals interpolated to this month.
    national_telephony = interpolate_yearly(
        MOBILE_TELEPHONY_SUBSCRIBERS_NATIONAL, period.year, period.month
    )
    national_internet = interpolate_yearly(
        MOBILE_INTERNET_SUBSCRIBERS_NATIONAL, period.year, period.month
    )

    # Apply seasonal factor.
    seasonal = seasonal_factor(period.month, amplitude=0.02)
    national_telephony *= seasonal
    national_internet *= seasonal

    mobile_ops = get_mobile_market_operators()
    internet_ops = get_mobile_internet_market_operators()

    # Allocate national totals to mobile operators.
    telephony_per_op = _allocate_to_operators(
        int(national_telephony), mobile_ops, "mobile_subscribers_2024"
    )
    internet_per_op = _allocate_to_operators(
        int(national_internet), internet_ops, "mobile_internet_subscribers_2024"
    )

    # Tech shares for this period.
    tech_share_2g = interpolate_yearly_dict(INTERNET_TECH_SHARES, period.year, period.month, "2G")
    tech_share_3g = interpolate_yearly_dict(INTERNET_TECH_SHARES, period.year, period.month, "3G")
    tech_share_4g = interpolate_yearly_dict(INTERNET_TECH_SHARES, period.year, period.month, "4G")

    for operator in mobile_ops:
        operator_id = operator.operator_id

        # Telephony: split by region, then prepaid/postpaid.
        telephony_by_region = _allocate_to_regions(telephony_per_op[operator_id], rng)
        for region_code, region_total in telephony_by_region.items():
            if region_total < 100:
                continue
            for payment_type, share in [("prepaid", PREPAID_SHARE), ("postpaid", POSTPAID_SHARE)]:
                seg_total = int(region_total * share)
                if seg_total < 10:
                    continue
                arpu = _arpu_for_segment(
                    "mobile_telephony", None, period, operator, rng
                )
                rows.append(_make_row(
                    operator_id, period, region_code,
                    "mobile",
                    "mobile_telephony", payment_type, None,
                    seg_total, arpu, rng,
                    source_file, line_counter, run_id,
                ))
                line_counter += 1

    # Internet: split by region, then by technology, then by prepaid/postpaid.
    for operator in internet_ops:
        operator_id = operator.operator_id
        internet_by_region = _allocate_to_regions(internet_per_op[operator_id], rng)
        for region_code, region_total in internet_by_region.items():
            if region_total < 100:
                continue
            for tech, share in [
                ("2G", tech_share_2g),
                ("3G", tech_share_3g),
                ("4G", tech_share_4g),
            ]:
                tech_total = int(region_total * share)
                if tech_total < 50:
                    continue
                for payment_type, p_share in [
                    ("prepaid", PREPAID_SHARE),
                    ("postpaid", POSTPAID_SHARE),
                ]:
                    seg_total = int(tech_total * p_share)
                    if seg_total < 10:
                        continue
                    arpu = _arpu_for_segment(
                        "mobile_internet", tech, period, operator, rng
                    )
                    rows.append(_make_row(
                        operator_id, period, region_code,
                        "mobile",
                        "mobile_internet", payment_type, tech,
                        seg_total, arpu, rng,
                        source_file, line_counter, run_id,
                    ))
                    line_counter += 1

    # Fixed voice: one state-owned fixed operator, mostly postpaid.
    for operator in get_fixed_voice_operators():
        operator_total = int(
            operator.fixed_subscribers_2024
            * ((1 + operator.mobile_growth_rate_annual) ** (period.year - 2024))
            * seasonal_factor(period.month, amplitude=0.01)
        )
        fixed_by_region = _allocate_to_regions(operator_total, rng)
        for region_code, region_total in fixed_by_region.items():
            if region_total < 20:
                continue
            arpu = _arpu_for_segment("fixed_voice", None, period, operator, rng)
            rows.append(_make_row(
                operator.operator_id, period, region_code,
                "fixed_voice",
                "fixed_voice", "postpaid", None,
                region_total, arpu, rng,
                source_file, line_counter, run_id,
            ))
            line_counter += 1

    # Fixed broadband: state fixed operator plus ISP operators.
    for operator in get_fixed_broadband_operators():
        anchor = operator.isp_subscribers_2024 or operator.fixed_subscribers_2024
        operator_total = int(
            anchor
            * ((1 + operator.internet_growth_rate_annual) ** (period.year - 2024))
            * seasonal_factor(period.month, amplitude=0.015)
        )
        broadband_by_region = _allocate_to_regions(operator_total, rng)
        for region_code, region_total in broadband_by_region.items():
            if region_total < 20:
                continue
            arpu = _arpu_for_segment("fixed_broadband", None, period, operator, rng)
            rows.append(_make_row(
                operator.operator_id, period, region_code,
                "fixed_broadband",
                "fixed_broadband", "postpaid", None,
                region_total, arpu, rng,
                source_file, line_counter, run_id,
            ))
            line_counter += 1

    logger.info(
        "generated_subscribers",
        period=period.period_str,
        rows=len(rows),
    )
    return rows


def rows_to_records(rows: list[SubscriberRow]) -> list[dict]:
    """Convert dataclass rows to dicts for DataFrame construction."""
    return [asdict(row) for row in rows]
