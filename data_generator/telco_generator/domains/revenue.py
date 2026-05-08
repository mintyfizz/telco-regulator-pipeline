"""
Revenue domain generator.

Produces bronze.revenue rows per (operator, period). Note: revenue is reported
nationally per operator, not regionally — matching how operators report to ARPCE.

Calibrated against ARPCE 2024 anchors:
- Total mobile internet revenue: 63.569B FCFA
- Total mobile telephony revenue: 128.891B FCFA (combined voice + SMS)
- 14 distinct revenue lines summing to total
- USF contribution: typically 3% of total revenue
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np

from telco_generator.constants.operators import get_mobile_internet_market_operators
from telco_generator.constants.trajectories import (
    INTERNET_TRAFFIC_SHARES,
    TOTAL_INTERNET_REVENUE_XAF,
)
from telco_generator.utils.interpolation import (
    interpolate_yearly,
    interpolate_yearly_dict,
)
from telco_generator.utils.logging import get_logger
from telco_generator.utils.noise import lognormal_noise, seasonal_factor
from telco_generator.utils.time import ReportingPeriod

logger = get_logger(__name__)

# Revenue split ratios (calibrated to ARPCE 2024 telephony report).
VOICE_OUTGOING_ONNET_RATIO = 0.708
VOICE_OUTGOING_OFFNET_RATIO = 0.138
VOICE_OUTGOING_INTL_RATIO = 0.020
VOICE_INCOMING_NATIONAL_RATIO = 0.036
VOICE_INCOMING_INTL_RATIO = 0.021
SMS_OUTGOING_ONNET_RATIO = 0.075
SMS_OUTGOING_OFFNET_RATIO = 0.0007
SMS_OUTGOING_INTL_RATIO = 0.0004
SMS_INCOMING_RATIO = 0.0004

VAS_RATIO = 0.05  # value-added services as fraction of voice/SMS revenue
OTHER_RATIO = 0.02
USF_CONTRIBUTION_RATE = 0.03  # 3% of total revenue

# Approximate 2024 telephony revenue (voice + SMS) per operator.
# Values sum to the 128.891B FCFA national anchor, so adding smaller operators
# redistributes the same market instead of increasing total market size.
TELEPHONY_REVENUE_2024 = {
    "OPA01": 92_000_000_000,
    "OPA02": 32_000_000_000,
    "OPA03": 1_900_000_000,
    "OPA04": 1_200_000_000,
    "OPA05": 800_000_000,
    "OPA06": 550_000_000,
    "OPA07": 441_000_000,
}


@dataclass
class RevenueRow:
    bronze_id: str
    source_submission_id: str
    operator_id: str
    report_period: str
    service_segment: str
    revenue_voice_outgoing_onnet_xaf: int
    revenue_voice_outgoing_offnet_xaf: int
    revenue_voice_outgoing_international_xaf: int
    revenue_voice_incoming_national_xaf: int
    revenue_voice_incoming_international_xaf: int
    revenue_sms_outgoing_onnet_xaf: int
    revenue_sms_outgoing_offnet_xaf: int
    revenue_sms_outgoing_international_xaf: int
    revenue_sms_incoming_xaf: int
    revenue_internet_2g_xaf: int
    revenue_internet_3g_xaf: int
    revenue_internet_4g_xaf: int
    revenue_internet_5g_xaf: int | None
    revenue_value_added_services_xaf: int
    revenue_other_xaf: int
    total_revenue_xaf: int
    usf_contribution_xaf: int
    submitted_at: str
    _source_file: str
    _source_line: int
    _loaded_at: str
    _loaded_by_run_id: str
    _raw_payload: str


def generate_revenue_for_period(
    period: ReportingPeriod,
    rng: np.random.Generator,
    run_id: str,
    source_file: str = "synthetic_revenue.csv",
) -> list[RevenueRow]:
    rows: list[RevenueRow] = []
    line_counter = 1

    # Internet revenue is interpolated from annual anchors.
    national_internet_annual = interpolate_yearly(
        TOTAL_INTERNET_REVENUE_XAF, period.year, period.month
    )
    monthly_internet = national_internet_annual / 12 * seasonal_factor(period.month, amplitude=0.03)

    # Internet revenue split by technology (matching traffic shares roughly).
    share_2g = interpolate_yearly_dict(INTERNET_TRAFFIC_SHARES, period.year, period.month, "2G")
    share_3g = interpolate_yearly_dict(INTERNET_TRAFFIC_SHARES, period.year, period.month, "3G")
    share_4g = interpolate_yearly_dict(INTERNET_TRAFFIC_SHARES, period.year, period.month, "4G")

    # Telephony revenue scales by year (approximate).
    year_factor = 1.0 + (period.year - 2024) * 0.02  # 2% annual change

    operators = get_mobile_internet_market_operators()

    # Internet revenue per operator (by internet subscriber share).
    total_internet_subs = sum(op.mobile_internet_subscribers_2024 for op in operators)

    for operator in operators:
        op_id = operator.operator_id

        # Internet revenue allocation.
        op_internet_share = operator.mobile_internet_subscribers_2024 / total_internet_subs
        op_monthly_internet = (
            monthly_internet
            * op_internet_share
            * lognormal_noise(rng, sigma=0.05)
        )

        rev_internet_2g = int(op_monthly_internet * share_2g * lognormal_noise(rng, sigma=0.15))
        rev_internet_3g = int(op_monthly_internet * share_3g * lognormal_noise(rng, sigma=0.08))
        rev_internet_4g = int(op_monthly_internet * share_4g * lognormal_noise(rng, sigma=0.06))

        # Telephony revenue: monthly portion of annual.
        annual_telephony = TELEPHONY_REVENUE_2024.get(op_id, 0) * year_factor
        monthly_telephony = annual_telephony / 12 * seasonal_factor(period.month, amplitude=0.04)
        monthly_telephony *= lognormal_noise(rng, sigma=0.05)

        rev_voice_onnet = int(
            monthly_telephony * VOICE_OUTGOING_ONNET_RATIO * lognormal_noise(rng, sigma=0.04)
        )
        rev_voice_offnet = int(
            monthly_telephony * VOICE_OUTGOING_OFFNET_RATIO * lognormal_noise(rng, sigma=0.08)
        )
        rev_voice_intl_out = int(
            monthly_telephony * VOICE_OUTGOING_INTL_RATIO * lognormal_noise(rng, sigma=0.12)
        )
        rev_voice_in_nat = int(
            monthly_telephony * VOICE_INCOMING_NATIONAL_RATIO * lognormal_noise(rng, sigma=0.10)
        )
        rev_voice_in_intl = int(
            monthly_telephony * VOICE_INCOMING_INTL_RATIO * lognormal_noise(rng, sigma=0.15)
        )

        rev_sms_onnet = int(
            monthly_telephony * SMS_OUTGOING_ONNET_RATIO * lognormal_noise(rng, sigma=0.06)
        )
        rev_sms_offnet = int(
            monthly_telephony * SMS_OUTGOING_OFFNET_RATIO * lognormal_noise(rng, sigma=0.20)
        )
        rev_sms_intl = int(
            monthly_telephony * SMS_OUTGOING_INTL_RATIO * lognormal_noise(rng, sigma=0.25)
        )
        rev_sms_in = int(monthly_telephony * SMS_INCOMING_RATIO * lognormal_noise(rng, sigma=0.20))

        rev_vas = int(
            (rev_voice_onnet + rev_voice_offnet + rev_sms_onnet)
            * VAS_RATIO
            * lognormal_noise(rng, sigma=0.10)
        )
        rev_other = int(
            (rev_voice_onnet + rev_voice_offnet)
            * OTHER_RATIO
            * lognormal_noise(rng, sigma=0.15)
        )

        # Total = sum of all components.
        total = (
            rev_voice_onnet + rev_voice_offnet + rev_voice_intl_out
            + rev_voice_in_nat + rev_voice_in_intl
            + rev_sms_onnet + rev_sms_offnet + rev_sms_intl + rev_sms_in
            + rev_internet_2g + rev_internet_3g + rev_internet_4g
            + rev_vas + rev_other
        )
        usf = int(total * USF_CONTRIBUTION_RATE)

        submission_id = f"REV-{op_id}-{period.period_str}"
        raw_payload = {
            "operator_id": op_id,
            "report_period": period.period_str,
            "service_segment": "mobile",
            "total_revenue_xaf": total,
        }

        rows.append(RevenueRow(
            bronze_id=str(uuid.uuid4()),
            source_submission_id=submission_id,
            operator_id=op_id,
            report_period=period.period_str,
            service_segment="mobile",
            revenue_voice_outgoing_onnet_xaf=rev_voice_onnet,
            revenue_voice_outgoing_offnet_xaf=rev_voice_offnet,
            revenue_voice_outgoing_international_xaf=rev_voice_intl_out,
            revenue_voice_incoming_national_xaf=rev_voice_in_nat,
            revenue_voice_incoming_international_xaf=rev_voice_in_intl,
            revenue_sms_outgoing_onnet_xaf=rev_sms_onnet,
            revenue_sms_outgoing_offnet_xaf=rev_sms_offnet,
            revenue_sms_outgoing_international_xaf=rev_sms_intl,
            revenue_sms_incoming_xaf=rev_sms_in,
            revenue_internet_2g_xaf=rev_internet_2g,
            revenue_internet_3g_xaf=rev_internet_3g,
            revenue_internet_4g_xaf=rev_internet_4g,
            revenue_internet_5g_xaf=None,
            revenue_value_added_services_xaf=rev_vas,
            revenue_other_xaf=rev_other,
            total_revenue_xaf=total,
            usf_contribution_xaf=usf,
            submitted_at=period.submission_timestamp().isoformat(),
            _source_file=source_file,
            _source_line=line_counter,
            _loaded_at=datetime.now().isoformat(),
            _loaded_by_run_id=run_id,
            _raw_payload=json.dumps(raw_payload),
        ))
        line_counter += 1

    logger.info("generated_revenue", period=period.period_str, rows=len(rows))
    return rows


def rows_to_records(rows: list[RevenueRow]) -> list[dict]:
    return [asdict(row) for row in rows]
