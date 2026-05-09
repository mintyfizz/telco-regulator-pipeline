import csv
import json
from pathlib import Path

import numpy as np
from telco_generator.anomalies import apply_controlled_anomalies
from telco_generator.config import GeneratorConfig
from telco_generator.orchestrator import run_generator


def test_run_generator_single_period_outputs_all_domains(tmp_path: Path) -> None:
    config = GeneratorConfig(
        period="2025-03",
        output_dir=tmp_path,
        random_seed=202503,
        anomaly_rate=0.0,
    )

    totals = run_generator(config)

    assert set(totals) == {
        "subscribers",
        "traffic_voice",
        "traffic_sms",
        "traffic_internet",
        "qos",
        "revenue",
    }
    assert all(count > 0 for count in totals.values())

    for domain in totals:
        csv_path = tmp_path / domain / "2025" / "2025-03.csv"
        assert csv_path.exists()
        with csv_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            first_row = next(reader)
            assert first_row["report_period"] == "2025-03"


def test_apply_controlled_anomalies_marks_raw_payload() -> None:
    records = [
        {
            "service_segment": "mobile",
            "total_subscribers": 100,
            "active_subscribers_30d": 90,
            "new_activations": 10,
            "churn_count": 2,
            "arpu_xaf": 1400.0,
            "_raw_payload": "{}",
        }
    ]

    changed = apply_controlled_anomalies(
        domain="subscribers",
        records=records,
        rng=np.random.default_rng(42),
        anomaly_rate=1.0,
    )

    assert changed == 1
    payload = json.loads(str(records[0]["_raw_payload"]))
    assert "_synthetic_anomaly" in payload
    assert payload["_synthetic_anomaly"]["domain"] == "subscribers"
