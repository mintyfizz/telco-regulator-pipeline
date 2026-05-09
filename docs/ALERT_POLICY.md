# Quality Alert Workflow Policy

## Scope

Threshold-driven alerts from `silver.evaluate_quality_alerts(report_period)` for domains:
- subscribers
- traffic_voice
- traffic_sms
- traffic_internet
- qos
- revenue

## Workflow

1. **Detection**: monthly run computes threshold breaches.
2. **Deduplication**: `alert_code + domain + report_period` represents one active alert event.
3. **Notification routing**:
   - critical -> data platform on-call + regulator analytics owner
   - warning -> regulator analytics owner queue
4. **Acknowledgment**: owner marks event acknowledged within agreed SLA.
5. **Resolution**: owner marks resolved after root-cause and remediation.

## Ownership Matrix

| Severity | Primary owner | Secondary owner |
|---|---|---|
| critical | Data platform on-call | Analytics lead |
| warning | Analytics lead | Domain steward |

## Review Cadence

- Monthly threshold review after each reporting cycle.
- Tune thresholds when false positives or missed incidents are identified.
- Keep historical threshold changes documented in migration history.
