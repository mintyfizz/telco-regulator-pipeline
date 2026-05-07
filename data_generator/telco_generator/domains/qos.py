"""
Quality of Service (QoS) domain generator.

Produces bronze.qos rows per (operator, period, region).

QoS is the most adversarial domain — operators have incentive to underreport
problems. The generator injects occasional "gaming" patterns: too-clean numbers,
suspicious round figures, unrealistic consistency. The validation layer in
Step 10 will be designed to catch these.

Realistic ranges:
- Network availability: 95-99.95% (urban higher, rural lower)
- Call drop rate: 0.5-6%
- 4G throughput: 8-45 Mbps
- 3G throughput: 0.5-7 Mbps
- Latency: 30-200ms
"""

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime

import numpy as np

from telco_generator.constants.operators import OPERATORS
from telco_generator.constants.regions import REGIONS
from telco_generator.utils.logging import get_logger
from telco_generator.utils.noise import normal_noise
from telco_generator.utils.time import ReportingPeriod

logger = get_logger(__name__)

# Base ranges per metric (urban anchors).
URBAN_AVAILABILITY = 99.5
URBAN_DROP_RATE = 1.2
URBAN_SETUP_SUCCESS = 98.5
URBAN_THROUGHPUT_4G = 28.0
URBAN_THROUGHPUT_3G = 4.5
URBAN_LATENCY = 55
URBAN_COVERAGE_4G = 92.0
URBAN_COVERAGE_3G = 99.0
URBAN_COVERAGE_2G = 99.9

# Rural penalty factors.
RURAL_AVAILABILITY_PENALTY = 2.5  # percentage points lower
RURAL_DROP_RATE_PENALTY = 2.0  # additive
RURAL_SETUP_PENALTY = 4.0  # subtractive
RURAL_THROUGHPUT_FACTOR = 0.4  # rural throughput is 40% of urban
RURAL_LATENCY_PENALTY = 80  # additive ms
RURAL_COVERAGE_4G_PENALTY = 35.0  # massive gap
RURAL_COVERAGE_3G_PENALTY = 18.0
RURAL_COVERAGE_2G_PENALTY = 5.0


@dataclass
class QosRow:
    bronze_id: str
    source_submission_id: str
    operator_id: str
    report_period: str
    region_code: str
    measurement_methodology: str
    period_type: str
    network_availability_pct: float
    call_drop_rate_pct: float
    call_setup_success_rate_pct: float
    avg_data_throughput_mbps_4g: float
    avg_data_throughput_mbps_3g: float
    avg_latency_ms: int
    population_coverage_pct_4g: float
    population_coverage_pct_3g: float
    population_coverage_pct_2g: float
    qos_related_complaints: int
    submitted_at: str
    _source_file: str
    _source_line: int
    _loaded_at: str
    _loaded_by_run_id: str
    _raw_payload: str


def _inject_gaming_pattern(value: float, rng: np.random.Generator) -> float:
    """Sometimes return a suspiciously round/clean value (gaming signal)."""
    rounded = round(value)
    return float(rounded) if rng.random() < 0.5 else round(value * 2) / 2


def generate_qos_for_period(
    period: ReportingPeriod,
    rng: np.random.Generator,
    run_id: str,
    qos_gaming_rate: float = 0.03,
    source_file: str = "synthetic_qos.csv",
) -> list[QosRow]:
    rows: list[QosRow] = []
    line_counter = 1

    operators = list(OPERATORS.values())

    for operator in operators:
        op_id = operator.operator_id
        quality_factor = operator.qos_quality_factor

        for region_code, region in REGIONS.items():
            is_urban = region.is_urban_concentration

            availability = URBAN_AVAILABILITY * quality_factor
            drop_rate = URBAN_DROP_RATE / quality_factor
            setup_success = URBAN_SETUP_SUCCESS * quality_factor
            throughput_4g = URBAN_THROUGHPUT_4G * quality_factor
            throughput_3g = URBAN_THROUGHPUT_3G * quality_factor
            latency = URBAN_LATENCY / quality_factor
            coverage_4g = URBAN_COVERAGE_4G
            coverage_3g = URBAN_COVERAGE_3G
            coverage_2g = URBAN_COVERAGE_2G

            if not is_urban:
                availability -= RURAL_AVAILABILITY_PENALTY
                drop_rate += RURAL_DROP_RATE_PENALTY
                setup_success -= RURAL_SETUP_PENALTY
                throughput_4g *= RURAL_THROUGHPUT_FACTOR
                throughput_3g *= RURAL_THROUGHPUT_FACTOR
                latency += RURAL_LATENCY_PENALTY
                coverage_4g -= RURAL_COVERAGE_4G_PENALTY
                coverage_3g -= RURAL_COVERAGE_3G_PENALTY
                coverage_2g -= RURAL_COVERAGE_2G_PENALTY

            # Apply noise.
            availability *= normal_noise(rng, sigma=0.005)
            drop_rate *= normal_noise(rng, sigma=0.15)
            setup_success *= normal_noise(rng, sigma=0.01)
            throughput_4g *= normal_noise(rng, sigma=0.12)
            throughput_3g *= normal_noise(rng, sigma=0.15)
            latency = int(latency * normal_noise(rng, sigma=0.10))
            coverage_4g *= normal_noise(rng, sigma=0.03)
            coverage_3g *= normal_noise(rng, sigma=0.02)
            coverage_2g *= normal_noise(rng, sigma=0.01)

            # Clamp to realistic bounds.
            availability = min(max(availability, 80.0), 99.99)
            drop_rate = min(max(drop_rate, 0.1), 15.0)
            setup_success = min(max(setup_success, 80.0), 99.99)
            coverage_4g = min(max(coverage_4g, 5.0), 99.9)
            coverage_3g = min(max(coverage_3g, 30.0), 100.0)
            coverage_2g = min(max(coverage_2g, 80.0), 100.0)

            # Decide methodology.
            methodology = (
                "operator_self_reported"
                if rng.random() < 0.85
                else "regulator_audit"
            )

            # Inject gaming pattern occasionally for self-reported.
            is_gamed = (
                methodology == "operator_self_reported"
                and rng.random() < qos_gaming_rate
            )
            if is_gamed:
                availability = _inject_gaming_pattern(availability, rng)
                drop_rate = _inject_gaming_pattern(drop_rate, rng)
                setup_success = _inject_gaming_pattern(setup_success, rng)

            # Complaints scale inversely with availability.
            base_complaints = int((100 - availability) * 5 * region.population_2023 / 1_000_000)
            complaints = max(0, int(base_complaints * normal_noise(rng, sigma=0.3)))

            submission_id = f"QOS-{op_id}-{period.period_str}-{region_code}"
            raw_payload = {
                "operator_id": op_id,
                "report_period": period.period_str,
                "region_code": region_code,
                "measurement_methodology": methodology,
                "period_type": "monthly",
                "network_availability_pct": round(availability, 3),
                "call_drop_rate_pct": round(drop_rate, 3),
                "call_setup_success_rate_pct": round(setup_success, 3),
                "avg_data_throughput_mbps_4g": round(throughput_4g, 3),
                "avg_data_throughput_mbps_3g": round(throughput_3g, 3),
                "avg_latency_ms": latency,
                "population_coverage_pct_4g": round(coverage_4g, 3),
                "population_coverage_pct_3g": round(coverage_3g, 3),
                "population_coverage_pct_2g": round(coverage_2g, 3),
                "qos_related_complaints": complaints,
                "_gamed": is_gamed,  # debugging marker, not in actual schema
            }

            rows.append(QosRow(
                bronze_id=str(uuid.uuid4()),
                source_submission_id=submission_id,
                operator_id=op_id,
                report_period=period.period_str,
                region_code=region_code,
                measurement_methodology=methodology,
                period_type="monthly",
                network_availability_pct=round(availability, 3),
                call_drop_rate_pct=round(drop_rate, 3),
                call_setup_success_rate_pct=round(setup_success, 3),
                avg_data_throughput_mbps_4g=round(throughput_4g, 3),
                avg_data_throughput_mbps_3g=round(throughput_3g, 3),
                avg_latency_ms=latency,
                population_coverage_pct_4g=round(coverage_4g, 3),
                population_coverage_pct_3g=round(coverage_3g, 3),
                population_coverage_pct_2g=round(coverage_2g, 3),
                qos_related_complaints=complaints,
                submitted_at=period.submission_timestamp().isoformat(),
                _source_file=source_file,
                _source_line=line_counter,
                _loaded_at=datetime.now().isoformat(),
                _loaded_by_run_id=run_id,
                _raw_payload=json.dumps(raw_payload),
            ))
            line_counter += 1

    logger.info("generated_qos", period=period.period_str, rows=len(rows))
    return rows


def rows_to_records(rows: list[QosRow]) -> list[dict]:
    return [asdict(row) for row in rows]
