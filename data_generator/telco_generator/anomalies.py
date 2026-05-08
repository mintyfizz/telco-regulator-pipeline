"""
Controlled anomaly injection for synthetic operator submissions.

These anomalies are intentionally rare and domain-aware. They preserve the
market structure and operator characteristics, but create realistic data
quality scenarios for silver/dbt validation and alerting.
"""

from __future__ import annotations

import json

import numpy as np

Record = dict[str, object]


def apply_controlled_anomalies(
    domain: str,
    records: list[Record],
    rng: np.random.Generator,
    anomaly_rate: float,
) -> int:
    """
    Mutate records in place with rare, controlled anomalies.

    Returns the number of rows modified. When anomaly_rate is 0, the generator
    remains a clean calibrated baseline.
    """
    if anomaly_rate <= 0 or not records:
        return 0

    anomalies_applied = 0
    for record in records:
        if rng.random() >= anomaly_rate:
            continue

        anomaly_code = _apply_domain_anomaly(domain, record, rng)
        if anomaly_code is not None:
            anomalies_applied += 1

    return anomalies_applied


def _apply_domain_anomaly(
    domain: str,
    record: Record,
    rng: np.random.Generator,
) -> str | None:
    if domain == "subscribers":
        return _apply_subscriber_anomaly(record, rng)
    if domain == "traffic_voice":
        return _apply_voice_anomaly(record, rng)
    if domain == "traffic_sms":
        return _apply_sms_anomaly(record, rng)
    if domain == "traffic_internet":
        return _apply_internet_anomaly(record, rng)
    if domain == "qos":
        return _apply_qos_anomaly(record, rng)
    if domain == "revenue":
        return _apply_revenue_anomaly(record, rng)
    return None


def _apply_subscriber_anomaly(record: Record, rng: np.random.Generator) -> str:
    choices = ("active_exceeds_total", "subscriber_spike", "arpu_spike")
    anomaly = str(rng.choice(choices))
    changed: dict[str, object] = {}

    if anomaly == "active_exceeds_total":
        total = max(_as_int(record.get("total_subscribers")), 1)
        changed["active_subscribers_30d"] = int(total * float(rng.uniform(1.08, 1.25)))
    elif anomaly == "subscriber_spike":
        factor = float(rng.uniform(1.8, 3.2))
        for field in (
            "total_subscribers",
            "active_subscribers_30d",
            "new_activations",
            "churn_count",
        ):
            changed[field] = int(_as_int(record.get(field)) * factor)
    else:
        arpu_factor = float(rng.uniform(2.2, 4.0))
        changed["arpu_xaf"] = round(_as_float(record.get("arpu_xaf")) * arpu_factor, 2)

    _apply_changes(record, "subscribers", anomaly, changed)
    return anomaly


def _apply_voice_anomaly(record: Record, rng: np.random.Generator) -> str:
    if rng.random() < 0.75:
        anomaly = "voice_traffic_spike"
        factor = float(rng.uniform(3.0, 6.0))
        fields = (
            "voice_minutes_outgoing_onnet",
            "voice_minutes_outgoing_offnet",
            "voice_minutes_outgoing_international",
            "voice_minutes_incoming_national",
            "voice_minutes_incoming_international",
            "voice_minutes_fixed_local",
            "voice_minutes_fixed_national",
            "voice_minutes_fixed_international_outgoing",
            "voice_minutes_fixed_incoming_national",
            "voice_minutes_fixed_incoming_international",
        )
        changed = _multiply_nonzero_integer_fields(record, fields, factor)
    else:
        anomaly = "voice_segment_metric_leak"
        if record.get("service_segment") == "mobile":
            leak_value = max(
                _as_int(record.get("voice_minutes_outgoing_onnet")) // 20,
                1,
            )
            changed = {"voice_minutes_fixed_local": leak_value}
        else:
            leak_value = max(
                _as_int(record.get("voice_minutes_fixed_local")) // 20,
                1,
            )
            changed = {"voice_minutes_outgoing_onnet": leak_value}

    _apply_changes(record, "traffic_voice", anomaly, changed)
    return anomaly


def _apply_sms_anomaly(record: Record, rng: np.random.Generator) -> str:
    if rng.random() < 0.75:
        anomaly = "sms_traffic_spike"
        factor = float(rng.uniform(4.0, 8.0))
        changed = _multiply_nonzero_integer_fields(
            record,
            (
                "sms_count_outgoing_onnet",
                "sms_count_outgoing_offnet",
                "sms_count_outgoing_international",
                "sms_count_incoming_national",
            ),
            factor,
        )
    else:
        anomaly = "sms_zero_outage"
        changed = {
            "sms_count_outgoing_onnet": 0,
            "sms_count_outgoing_offnet": 0,
            "sms_count_outgoing_international": 0,
            "sms_count_incoming_national": 0,
        }

    _apply_changes(record, "traffic_sms", anomaly, changed)
    return anomaly


def _apply_internet_anomaly(record: Record, rng: np.random.Generator) -> str:
    if rng.random() < 0.8:
        anomaly = "internet_traffic_spike"
        factor = float(rng.uniform(3.0, 7.0))
        changed = _multiply_nonzero_float_fields(
            record,
            (
                "data_consumed_mb_2g",
                "data_consumed_mb_3g",
                "data_consumed_mb_4g",
                "data_consumed_mb_5g",
                "data_consumed_mb_fiber",
                "data_consumed_mb_adsl",
                "data_consumed_mb_fixed_wireless",
            ),
            factor,
        )
    else:
        anomaly = "internet_segment_metric_leak"
        if record.get("service_segment") == "mobile":
            leak_value = round(
                max(_as_float(record.get("data_consumed_mb_4g")) * 0.01, 1.0),
                3,
            )
            changed = {"data_consumed_mb_fiber": leak_value}
        else:
            leak_value = round(
                max(_as_float(record.get("data_consumed_mb_fiber")) * 0.01, 1.0),
                3,
            )
            changed = {"data_consumed_mb_4g": leak_value}

    _apply_changes(record, "traffic_internet", anomaly, changed)
    return anomaly


def _apply_qos_anomaly(record: Record, rng: np.random.Generator) -> str:
    choices = ("qos_perfect_report", "qos_degradation", "complaint_spike")
    anomaly = str(rng.choice(choices))

    if anomaly == "qos_perfect_report":
        changed = {"network_availability_pct": 100.0}
        if record.get("service_segment") == "mobile":
            changed.update({
                "call_drop_rate_pct": 0.0,
                "call_setup_success_rate_pct": 100.0,
            })
        if record.get("service_segment") == "fixed_broadband":
            changed.update({
                "avg_packet_loss_pct": 0.0,
                "fixed_service_repair_time_hours": 0.5,
            })
    elif anomaly == "qos_degradation":
        changed = {
            "network_availability_pct": round(
                max(_as_float(record.get("network_availability_pct")) * 0.72, 40.0),
                3,
            ),
            "qos_related_complaints": max(_as_int(record.get("qos_related_complaints")) * 8, 1),
        }
        if record.get("avg_latency_ms") is not None:
            changed["avg_latency_ms"] = max(_as_int(record.get("avg_latency_ms")) * 3, 1)
        if record.get("fixed_service_repair_time_hours") is not None:
            changed["fixed_service_repair_time_hours"] = round(
                _as_float(record.get("fixed_service_repair_time_hours")) * 4.0,
                3,
            )
    else:
        complaints = max(_as_int(record.get("qos_related_complaints")) * 12, 1)
        changed = {"qos_related_complaints": complaints}

    _apply_changes(record, "qos", anomaly, changed)
    return anomaly


def _apply_revenue_anomaly(record: Record, rng: np.random.Generator) -> str:
    choices = ("component_sum_mismatch", "usf_rate_high", "revenue_spike")
    anomaly = str(rng.choice(choices))
    total = max(_as_int(record.get("total_revenue_xaf")), 1)

    if anomaly == "component_sum_mismatch":
        changed = {"total_revenue_xaf": int(total * float(rng.uniform(1.05, 1.12)))}
    elif anomaly == "usf_rate_high":
        changed = {"usf_contribution_xaf": int(total * float(rng.uniform(0.12, 0.18)))}
    else:
        factor = float(rng.uniform(2.0, 4.0))
        revenue_fields = tuple(
            field for field in record
            if field.startswith("revenue_") and field.endswith("_xaf")
        )
        changed = _multiply_nonzero_integer_fields(record, revenue_fields, factor)
        changed["total_revenue_xaf"] = int(total * factor)
        changed["usf_contribution_xaf"] = int(
            _as_int(record.get("usf_contribution_xaf")) * factor
        )

    _apply_changes(record, "revenue", anomaly, changed)
    return anomaly


def _multiply_nonzero_integer_fields(
    record: Record,
    fields: tuple[str, ...],
    factor: float,
) -> dict[str, int]:
    changed: dict[str, int] = {}
    for field in fields:
        value = record.get(field)
        if value is None:
            continue
        integer_value = _as_int(value)
        if integer_value > 0:
            changed[field] = int(integer_value * factor)
    return changed


def _multiply_nonzero_float_fields(
    record: Record,
    fields: tuple[str, ...],
    factor: float,
) -> dict[str, float]:
    changed: dict[str, float] = {}
    for field in fields:
        value = record.get(field)
        if value is None:
            continue
        float_value = _as_float(value)
        if float_value > 0:
            changed[field] = round(float_value * factor, 3)
    return changed


def _apply_changes(
    record: Record,
    domain: str,
    anomaly_code: str,
    changed: dict[str, object],
) -> None:
    record.update(changed)
    _update_raw_payload(record, domain, anomaly_code, changed)


def _update_raw_payload(
    record: Record,
    domain: str,
    anomaly_code: str,
    changed: dict[str, object],
) -> None:
    raw_payload = record.get("_raw_payload")
    payload: dict[str, object]
    if isinstance(raw_payload, str):
        try:
            loaded = json.loads(raw_payload)
            payload = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    payload.update(changed)
    payload["_synthetic_anomaly"] = {
        "domain": domain,
        "code": anomaly_code,
        "changed_fields": sorted(changed),
    }
    record["_raw_payload"] = json.dumps(payload, ensure_ascii=False)


def _as_int(value: object) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def _as_float(value: object) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)
