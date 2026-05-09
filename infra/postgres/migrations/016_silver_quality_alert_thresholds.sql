-- ============================================================================
-- 016_silver_quality_alert_thresholds.sql
-- Alert-threshold foundation for critical data-quality monitoring workflows.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.quality_alert_thresholds (
    threshold_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain               VARCHAR(40) NOT NULL,
    severity             VARCHAR(20) NOT NULL
                           CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    event_count_threshold INTEGER NOT NULL CHECK (event_count_threshold > 0),
    enabled              BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (domain, severity)
);

INSERT INTO silver.quality_alert_thresholds (domain, severity, event_count_threshold, enabled)
VALUES
    ('subscribers', 'critical', 10, TRUE),
    ('traffic_voice', 'critical', 10, TRUE),
    ('traffic_sms', 'critical', 10, TRUE),
    ('traffic_internet', 'critical', 10, TRUE),
    ('qos', 'critical', 10, TRUE),
    ('revenue', 'critical', 10, TRUE)
ON CONFLICT (domain, severity) DO NOTHING;

CREATE OR REPLACE FUNCTION silver.evaluate_quality_alerts(
    p_report_period VARCHAR(7)
) RETURNS TABLE (
    alert_code TEXT,
    severity VARCHAR(20),
    domain VARCHAR(40),
    report_period VARCHAR(7),
    event_count BIGINT,
    threshold_value INTEGER
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        'quality_events_threshold_exceeded'::TEXT AS alert_code,
        t.severity,
        t.domain,
        p_report_period,
        COUNT(e.event_id)::BIGINT AS event_count,
        t.event_count_threshold AS threshold_value
    FROM silver.quality_alert_thresholds t
    LEFT JOIN silver.data_quality_events e
        ON e.domain = t.domain
       AND e.severity = t.severity
       AND e.status IN ('open', 'acknowledged')
       AND e.report_period = p_report_period
    WHERE t.enabled = TRUE
    GROUP BY t.domain, t.severity, t.event_count_threshold
    HAVING COUNT(e.event_id) >= t.event_count_threshold
    ORDER BY t.domain, t.severity;
END;
$$;

COMMENT ON FUNCTION silver.evaluate_quality_alerts IS
'Return period-level quality alert candidates when open/acknowledged event counts meet configured severity thresholds.';
