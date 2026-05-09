from datetime import UTC, datetime

from telco_generator.pipeline_runtime import (
    build_generation_decision,
    collect_validation_snapshot,
    persist_run_metrics,
    resolve_generation_parameters,
)


def test_build_generation_decision_loaded() -> None:
    decision = build_generation_decision(
        period="2025-03",
        status="loaded",
        loaded_domains=["subscribers", "qos"],
    )
    assert decision["generated"] is False
    assert "fully loaded" in str(decision["reason"])


def test_build_generation_decision_partial_raises() -> None:
    try:
        build_generation_decision(
            period="2025-03",
            status="partial",
            loaded_domains=["subscribers"],
        )
    except ValueError as exc:
        assert "partial data" in str(exc)
        assert "subscribers" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_resolve_generation_parameters_defaults_seed_to_period() -> None:
    anomaly_rate, seed = resolve_generation_parameters(period="2025-03", params={})
    assert anomaly_rate == 0.0
    assert seed == 202503


class _FakeHook:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...] | None]] = []
        loaded_after = datetime(2025, 3, 1, 0, 0, tzinfo=UTC)
        self.responses = [
            [(loaded_after,)],
            [("subscribers", 10, 9, 1), ("qos", 5, 5, 0)],
            [(3,)],
            [("subscribers", 10), ("qos", 5)],
            [("subscribers", 1), ("qos", 0)],
            [("quality_events_threshold_exceeded", "critical", "subscribers", "2025-03", 12, 10)],
            [("2025-03",)],
        ]

    def get_records(
        self,
        sql: str,
        parameters: tuple[object, ...] | None = None,
    ) -> list[tuple[object, ...]]:
        self.calls.append((sql, parameters))
        return self.responses.pop(0)


def test_collect_validation_snapshot_uses_incremental_window_and_alert_eval() -> None:
    hook = _FakeHook()
    snapshot = collect_validation_snapshot(
        hook=hook,
        period="2025-03",
        validation_started_at=datetime(2025, 4, 5, 3, 0, tzinfo=UTC),
    )

    assert snapshot["validation_window_start"] == "2025-03-01T00:00:00+00:00"
    assert snapshot["events_captured"] == 3
    assert len(snapshot["alerts"]) == 1
    assert "run_all_validations" in hook.calls[1][0]
    assert hook.calls[1][1] == (None, datetime(2025, 3, 1, 0, 0, tzinfo=UTC))
    assert "capture_suspicious_anomaly_events" in hook.calls[2][0]
    assert hook.calls[2][1] == (None, datetime(2025, 3, 1, 0, 0, tzinfo=UTC))
    assert "evaluate_quality_alerts" in hook.calls[5][0]
    assert hook.calls[5][1] == ("2025-03",)


def test_persist_run_metrics_aggregates_totals() -> None:
    hook = _FakeHook()
    snapshot = collect_validation_snapshot(
        hook=hook,
        period="2025-03",
        validation_started_at=datetime(2025, 4, 5, 3, 0, tzinfo=UTC),
    )
    persist_run_metrics(hook=hook, snapshot=snapshot)
    sql, params = hook.calls[-1]
    assert "monthly_reporting_run_metrics" in sql
    assert params is not None
    assert params[3] == 15
    assert params[4] == 15
    assert params[5] == 14
    assert params[6] == 1
    assert params[8] == 1
