"""Pure decision and runtime helpers shared by monthly orchestration logic and tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any, Protocol

REQUIRED_DOMAINS: tuple[str, ...] = (
    "subscribers",
    "traffic_voice",
    "traffic_sms",
    "traffic_internet",
    "qos",
    "revenue",
)


class RecordsHook(Protocol):
    """Subset of PostgresHook used by runtime helpers."""

    def get_records(
        self,
        sql: str,
        parameters: tuple[Any, ...] | None = None,
    ) -> list[tuple[Any, ...]]: ...


def classify_period_status(
    counts: dict[str, int],
    required_domains: tuple[str, ...] = REQUIRED_DOMAINS,
) -> str:
    """Classify monthly period state as loaded, partial, or empty."""
    loaded = [domain for domain in required_domains if int(counts.get(domain, 0)) > 0]
    if len(loaded) == len(required_domains):
        return "loaded"
    if loaded:
        return "partial"
    return "empty"


def build_generation_decision(
    period: str,
    status: str,
    loaded_domains: list[str],
) -> dict[str, Any]:
    """Return generation decision for period status or raise on partial loads."""
    if status == "loaded":
        return {
            "period": period,
            "generated": False,
            "reason": "period already fully loaded in bronze",
        }
    if status == "partial":
        raise ValueError(
            f"Refusing to auto-generate {period}: bronze already has partial data "
            f"for domains {loaded_domains}. Clean up or handle manually."
        )
    return {"period": period, "generated": True}


def resolve_generation_parameters(period: str, params: dict[str, Any]) -> tuple[float, int]:
    """Return anomaly rate and deterministic seed for generation runtime."""
    anomaly_rate = float(params.get("anomaly_rate") or 0.0)
    seed_param = params.get("seed")
    seed = int(seed_param) if seed_param is not None else int(period.replace("-", ""))
    return anomaly_rate, seed


def collect_validation_snapshot(
    hook: RecordsHook,
    period: str,
    validation_started_at: datetime,
) -> dict[str, Any]:
    """Run validation/event/alert queries and return run-level metrics."""
    started_at = validation_started_at.astimezone(UTC)

    min_loaded_at_rows = hook.get_records(
        """
        SELECT MIN(loaded_at) FROM (
            SELECT MIN(_loaded_at) AS loaded_at FROM bronze.subscribers WHERE report_period = %s
            UNION ALL
            SELECT MIN(_loaded_at) FROM bronze.traffic_voice WHERE report_period = %s
            UNION ALL
            SELECT MIN(_loaded_at) FROM bronze.traffic_sms WHERE report_period = %s
            UNION ALL
            SELECT MIN(_loaded_at) FROM bronze.traffic_internet WHERE report_period = %s
            UNION ALL
            SELECT MIN(_loaded_at) FROM bronze.qos WHERE report_period = %s
            UNION ALL
            SELECT MIN(_loaded_at) FROM bronze.revenue WHERE report_period = %s
        ) t
        """,
        parameters=(period, period, period, period, period, period),
    )
    loaded_after = min_loaded_at_rows[0][0] if min_loaded_at_rows else None

    rows = hook.get_records(
        "SELECT * FROM silver.run_all_validations(%s, %s);",
        parameters=(None, loaded_after),
    )
    event_rows = hook.get_records(
        "SELECT silver.capture_suspicious_anomaly_events(%s, %s);",
        parameters=(None, loaded_after),
    )
    event_count = int(event_rows[0][0]) if event_rows else 0

    bronze_rows = hook.get_records(
        """
        SELECT domain, row_count FROM (
            SELECT 'subscribers' AS domain, COUNT(*)::BIGINT AS row_count
            FROM bronze.subscribers
            WHERE report_period = %s
            UNION ALL
            SELECT 'traffic_voice', COUNT(*)::BIGINT
            FROM bronze.traffic_voice
            WHERE report_period = %s
            UNION ALL
            SELECT 'traffic_sms', COUNT(*)::BIGINT
            FROM bronze.traffic_sms
            WHERE report_period = %s
            UNION ALL
            SELECT 'traffic_internet', COUNT(*)::BIGINT
            FROM bronze.traffic_internet
            WHERE report_period = %s
            UNION ALL
            SELECT 'qos', COUNT(*)::BIGINT
            FROM bronze.qos
            WHERE report_period = %s
            UNION ALL
            SELECT 'revenue', COUNT(*)::BIGINT
            FROM bronze.revenue
            WHERE report_period = %s
        ) t
        ORDER BY domain
        """,
        parameters=(period, period, period, period, period, period),
    )

    rejection_rows = hook.get_records(
        """
        SELECT domain, rejected_count FROM (
            SELECT 'subscribers' AS domain, COUNT(*)::BIGINT AS rejected_count
            FROM silver.subscribers_rejections r
            JOIN bronze.subscribers b ON b.bronze_id = r.bronze_id
            WHERE b.report_period = %s
            UNION ALL
            SELECT 'traffic_voice', COUNT(*)::BIGINT
            FROM silver.traffic_voice_rejections r
            JOIN bronze.traffic_voice b ON b.bronze_id = r.bronze_id
            WHERE b.report_period = %s
            UNION ALL
            SELECT 'traffic_sms', COUNT(*)::BIGINT
            FROM silver.traffic_sms_rejections r
            JOIN bronze.traffic_sms b ON b.bronze_id = r.bronze_id
            WHERE b.report_period = %s
            UNION ALL
            SELECT 'traffic_internet', COUNT(*)::BIGINT
            FROM silver.traffic_internet_rejections r
            JOIN bronze.traffic_internet b ON b.bronze_id = r.bronze_id
            WHERE b.report_period = %s
            UNION ALL
            SELECT 'qos', COUNT(*)::BIGINT
            FROM silver.qos_rejections r
            JOIN bronze.qos b ON b.bronze_id = r.bronze_id
            WHERE b.report_period = %s
            UNION ALL
            SELECT 'revenue', COUNT(*)::BIGINT
            FROM silver.revenue_rejections r
            JOIN bronze.revenue b ON b.bronze_id = r.bronze_id
            WHERE b.report_period = %s
        ) t
        ORDER BY domain
        """,
        parameters=(period, period, period, period, period, period),
    )

    alerts = hook.get_records(
        (
            "SELECT alert_code, severity, domain, report_period, "
            "event_count, threshold_value "
            "FROM silver.evaluate_quality_alerts(%s);"
        ),
        parameters=(period,),
    )

    validation_results = [
        {
            "domain": domain,
            "rows_processed": int(rows_processed),
            "rows_validated": int(rows_validated),
            "rows_rejected": int(rows_rejected),
        }
        for domain, rows_processed, rows_validated, rows_rejected in rows
    ]
    bronze_by_domain = {domain: int(count) for domain, count in bronze_rows}
    rejections_by_domain = {domain: int(count) for domain, count in rejection_rows}

    return {
        "period": period,
        "validation_window_start": loaded_after.isoformat() if loaded_after else None,
        "validation_started_at": started_at.isoformat(),
        "validation_results": validation_results,
        "events_captured": event_count,
        "bronze_rows_by_domain": bronze_by_domain,
        "rejections_by_domain": rejections_by_domain,
        "alerts": [
            {
                "alert_code": alert_code,
                "severity": severity,
                "domain": domain,
                "report_period": report_period,
                "event_count": int(event_count),
                "threshold_value": int(threshold_value),
            }
            for (
                alert_code,
                severity,
                domain,
                report_period,
                event_count,
                threshold_value,
            ) in alerts
        ],
    }


def persist_run_metrics(hook: RecordsHook, snapshot: dict[str, Any]) -> None:
    """Persist per-period validation summary into the audit monthly metrics table."""
    validation_results = snapshot.get("validation_results", [])
    rows_processed = sum(int(item["rows_processed"]) for item in validation_results)
    rows_validated = sum(int(item["rows_validated"]) for item in validation_results)
    rows_rejected = sum(int(item["rows_rejected"]) for item in validation_results)
    rows_ingested = sum(int(v) for v in snapshot.get("bronze_rows_by_domain", {}).values())
    alerts_triggered = len(snapshot.get("alerts", []))

    hook.get_records(
        """
        INSERT INTO audit.monthly_reporting_run_metrics (
            report_period,
            validation_window_start,
            validation_started_at,
            rows_ingested,
            rows_processed,
            rows_validated,
            rows_rejected,
            events_captured,
            alerts_triggered,
            bronze_rows_by_domain,
            rejections_by_domain,
            validation_results
        )
        VALUES (
            %s, %s::timestamptz, %s::timestamptz, %s, %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb, %s::jsonb
        )
        ON CONFLICT (report_period) DO UPDATE
        SET
            validation_window_start = EXCLUDED.validation_window_start,
            validation_started_at = EXCLUDED.validation_started_at,
            rows_ingested = EXCLUDED.rows_ingested,
            rows_processed = EXCLUDED.rows_processed,
            rows_validated = EXCLUDED.rows_validated,
            rows_rejected = EXCLUDED.rows_rejected,
            events_captured = EXCLUDED.events_captured,
            alerts_triggered = EXCLUDED.alerts_triggered,
            bronze_rows_by_domain = EXCLUDED.bronze_rows_by_domain,
            rejections_by_domain = EXCLUDED.rejections_by_domain,
            validation_results = EXCLUDED.validation_results,
            updated_at = NOW()
        RETURNING report_period;
        """,
        parameters=(
            str(snapshot["period"]),
            snapshot.get("validation_window_start"),
            str(snapshot["validation_started_at"]),
            rows_ingested,
            rows_processed,
            rows_validated,
            rows_rejected,
            int(snapshot.get("events_captured") or 0),
            alerts_triggered,
            json.dumps(snapshot.get("bronze_rows_by_domain", {})),
            json.dumps(snapshot.get("rejections_by_domain", {})),
            json.dumps(validation_results),
        ),
    )
