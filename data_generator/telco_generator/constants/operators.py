"""
Operator profiles calibrated against ARPCE 2024 market reports.

Market share weights drive subscriber/traffic/revenue distribution.
Trajectory parameters shape 5-year evolution.

The two largest operators reflect the Congolese mobile duopoly market shape
without using real names. Fixed and ISP operators emit fixed_voice and
fixed_broadband submissions so the pipeline models all currently licensed
segments in the fictional operator catalog.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class OperatorProfile:
    """Calibration parameters for a single operator across the 5-year period."""

    operator_id: str
    operator_name: str
    operator_type: str  # mobile, fixed, isp
    service_segments: tuple[str, ...]
    is_state_owned: bool

    # 2024 market-share weights. The generator normalizes these weights against
    # national totals, so adding smaller operators does not increase market size.
    mobile_subscribers_2024: int
    mobile_internet_subscribers_2024: int
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
# National mobile totals remain 6.050M mobile telephony subscribers and 3.757M
# mobile internet subscribers. Fixed and ISP subscriber counts are synthetic
# local-market anchors because public ARPCE reports used for calibration focus
# on mobile. They are intentionally smaller and concentrated in urban regions.
OPERATORS: dict[str, OperatorProfile] = {
    "OPA01": OperatorProfile(
        operator_id="OPA01",
        operator_name="Mokongo Mobile",
        operator_type="mobile",
        service_segments=("mobile",),
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
        service_segments=("mobile",),
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
        service_segments=("fixed_voice", "fixed_broadband"),
        is_state_owned=True,
        mobile_subscribers_2024=0,
        mobile_internet_subscribers_2024=0,
        fixed_subscribers_2024=85_000,
        isp_subscribers_2024=65_000,
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
        service_segments=("fixed_broadband",),
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
        service_segments=("fixed_broadband",),
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
        service_segments=("fixed_broadband",),
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
        service_segments=("fixed_broadband",),
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
    """Return legally mobile operators."""
    return [op for op in OPERATORS.values() if op.operator_type == "mobile"]


def get_mobile_market_operators() -> list[OperatorProfile]:
    """Return operators participating in generated mobile-market allocation."""
    return [
        op for op in OPERATORS.values()
        if op.operator_type == "mobile" and op.mobile_subscribers_2024 > 0
    ]


def get_mobile_internet_market_operators() -> list[OperatorProfile]:
    """Return operators participating in generated mobile-internet allocation."""
    return [
        op for op in OPERATORS.values()
        if op.operator_type == "mobile" and op.mobile_internet_subscribers_2024 > 0
    ]


def get_internet_capable_operators() -> list[OperatorProfile]:
    """Return operators that provide internet (mobile + ISP)."""
    return [
        op for op in OPERATORS.values()
        if "mobile" in op.service_segments or "fixed_broadband" in op.service_segments
    ]


def get_fixed_voice_operators() -> list[OperatorProfile]:
    """Return operators licensed for fixed voice services."""
    return [op for op in OPERATORS.values() if "fixed_voice" in op.service_segments]


def get_fixed_broadband_operators() -> list[OperatorProfile]:
    """Return operators licensed for fixed broadband services."""
    return [op for op in OPERATORS.values() if "fixed_broadband" in op.service_segments]


def get_segment_operators(service_segment: str) -> list[OperatorProfile]:
    """Return operators licensed for the requested service segment."""
    return [op for op in OPERATORS.values() if service_segment in op.service_segments]


def get_operator(operator_id: str) -> OperatorProfile:
    """Look up a single operator profile by ID."""
    if operator_id not in OPERATORS:
        raise KeyError(f"Unknown operator_id: {operator_id}")
    return OPERATORS[operator_id]
