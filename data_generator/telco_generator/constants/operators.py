"""
Operator profiles calibrated against ARPCE 2024 market reports.

Market share weights drive subscriber/traffic/revenue distribution.
Trajectory parameters shape 5-year evolution.

The two mobile operators reflect the real Congolese duopoly structure
(MTN ~62%, Airtel ~38% subscriber share) without using real names.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorProfile:
    """Calibration parameters for a single operator across the 5-year period."""

    operator_id: str
    operator_name: str
    operator_type: str  # mobile, fixed, isp
    is_state_owned: bool

    # 2024 anchor values from ARPCE reports.
    mobile_subscribers_2024: int  # 0 if not a mobile operator
    mobile_internet_subscribers_2024: int  # 0 if not internet-capable
    fixed_subscribers_2024: int  # 0 if not fixed
    isp_subscribers_2024: int  # 0 if not ISP

    # Market dynamics.
    mobile_growth_rate_annual: float  # e.g., 0.02 = 2% growth per year
    internet_growth_rate_annual: float
    market_position: str  # leader, challenger, niche

    # Pricing and quality character.
    arpu_premium_factor: float  # 1.0 = average, 1.2 = 20% above average
    qos_quality_factor: float  # 1.0 = average reliability, lower = worse


# Calibrated to ARPCE 2024 reports.
# Total mobile telephony subscribers nationally: 6.050M
# Total mobile internet subscribers nationally: 3.757M
OPERATORS: dict[str, OperatorProfile] = {
    "OPA01": OperatorProfile(
        operator_id="OPA01",
        operator_name="Mokongo Mobile",
        operator_type="mobile",
        is_state_owned=False,
        mobile_subscribers_2024=3_761_000,
        mobile_internet_subscribers_2024=2_680_000,
        fixed_subscribers_2024=0,
        isp_subscribers_2024=0,
        mobile_growth_rate_annual=0.025,
        internet_growth_rate_annual=0.10,
        market_position="leader",
        arpu_premium_factor=0.92,  # Larger base, lower per-user spend
        qos_quality_factor=1.0,
    ),
    "OPA02": OperatorProfile(
        operator_id="OPA02",
        operator_name="Sangha Telecom",
        operator_type="mobile",
        is_state_owned=False,
        mobile_subscribers_2024=2_288_000,
        mobile_internet_subscribers_2024=1_077_000,
        fixed_subscribers_2024=0,
        isp_subscribers_2024=0,
        mobile_growth_rate_annual=-0.015,  # Slowly losing share
        internet_growth_rate_annual=0.05,
        market_position="challenger",
        arpu_premium_factor=1.10,  # Smaller base, higher per-user spend
        qos_quality_factor=0.95,
    ),
    "OPA03": OperatorProfile(
        operator_id="OPA03",
        operator_name="Congo Réseau",
        operator_type="fixed",
        is_state_owned=True,
        mobile_subscribers_2024=0,
        mobile_internet_subscribers_2024=0,
        fixed_subscribers_2024=85_000,
        isp_subscribers_2024=0,
        mobile_growth_rate_annual=0.0,
        internet_growth_rate_annual=0.03,
        market_position="leader",  # Dominant in fixed
        arpu_premium_factor=1.05,
        qos_quality_factor=0.85,  # Legacy infrastructure quality issues
    ),
    "OPA04": OperatorProfile(
        operator_id="OPA04",
        operator_name="Avenir Net",
        operator_type="isp",
        is_state_owned=False,
        mobile_subscribers_2024=0,
        mobile_internet_subscribers_2024=0,
        fixed_subscribers_2024=0,
        isp_subscribers_2024=120_000,
        mobile_growth_rate_annual=0.0,
        internet_growth_rate_annual=0.15,
        market_position="leader",
        arpu_premium_factor=1.20,
        qos_quality_factor=1.05,
    ),
    "OPA05": OperatorProfile(
        operator_id="OPA05",
        operator_name="Likouala Connect",
        operator_type="isp",
        is_state_owned=False,
        mobile_subscribers_2024=0,
        mobile_internet_subscribers_2024=0,
        fixed_subscribers_2024=0,
        isp_subscribers_2024=75_000,
        mobile_growth_rate_annual=0.0,
        internet_growth_rate_annual=0.18,
        market_position="challenger",
        arpu_premium_factor=1.15,
        qos_quality_factor=1.00,
    ),
    "OPA06": OperatorProfile(
        operator_id="OPA06",
        operator_name="Niari Web",
        operator_type="isp",
        is_state_owned=False,
        mobile_subscribers_2024=0,
        mobile_internet_subscribers_2024=0,
        fixed_subscribers_2024=0,
        isp_subscribers_2024=45_000,
        mobile_growth_rate_annual=0.0,
        internet_growth_rate_annual=0.22,
        market_position="niche",
        arpu_premium_factor=1.10,
        qos_quality_factor=0.95,
    ),
    "OPA07": OperatorProfile(
        operator_id="OPA07",
        operator_name="Plateaux Digital",
        operator_type="isp",
        is_state_owned=False,
        mobile_subscribers_2024=0,
        mobile_internet_subscribers_2024=0,
        fixed_subscribers_2024=0,
        isp_subscribers_2024=28_000,
        mobile_growth_rate_annual=0.0,
        internet_growth_rate_annual=0.30,  # Newest, fastest growth
        market_position="niche",
        arpu_premium_factor=1.05,
        qos_quality_factor=0.90,
    ),
}


def get_mobile_operators() -> list[OperatorProfile]:
    """Return only mobile operators."""
    return [op for op in OPERATORS.values() if op.operator_type == "mobile"]


def get_internet_capable_operators() -> list[OperatorProfile]:
    """Return operators that provide internet (mobile + ISP)."""
    return [
        op for op in OPERATORS.values()
        if op.operator_type in ("mobile", "isp")
    ]


def get_operator(operator_id: str) -> OperatorProfile:
    """Look up a single operator profile by ID."""
    if operator_id not in OPERATORS:
        raise KeyError(f"Unknown operator_id: {operator_id}")
    return OPERATORS[operator_id]