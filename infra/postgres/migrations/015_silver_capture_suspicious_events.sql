-- ============================================================================
-- 015_silver_capture_suspicious_events.sql
-- Capture suspicious synthetic anomaly markers as quality events.
--
-- Hard integrity violations remain in rejection tables. This migration captures
-- suspicious-but-valid records into silver.data_quality_events for dashboards
-- and alerting workflows.
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'silver.subscribers'::regclass
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%arpu_xaf <= 50000%'
    ) THEN
        EXECUTE (
            SELECT format('ALTER TABLE silver.subscribers DROP CONSTRAINT %I', c.conname)
            FROM pg_constraint c
            WHERE c.conrelid = 'silver.subscribers'::regclass
              AND c.contype = 'c'
              AND pg_get_constraintdef(c.oid) ILIKE '%arpu_xaf <= 50000%'
            LIMIT 1
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        WHERE c.conrelid = 'silver.subscribers'::regclass
          AND c.conname = 'chk_silver_subscribers_arpu_nonnegative'
    ) THEN
        ALTER TABLE silver.subscribers
        ADD CONSTRAINT chk_silver_subscribers_arpu_nonnegative
        CHECK (arpu_xaf >= 0);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION silver.capture_suspicious_anomaly_events(
    p_run_id UUID DEFAULT NULL,
    p_bronze_loaded_after TIMESTAMPTZ DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_events BIGINT := 0;
BEGIN
    WITH anomaly_rows AS (
        SELECT
            'subscribers'::TEXT AS domain,
            s.operator_id,
            s.service_segment,
            s.report_period,
            s.region_code,
            'silver.subscribers'::VARCHAR(80) AS source_table,
            s.silver_id AS source_id,
            s.bronze_id,
            b._raw_payload -> '_synthetic_anomaly' ->> 'code' AS anomaly_code,
            b._raw_payload -> '_synthetic_anomaly' -> 'changed_fields' AS changed_fields,
            s.arpu_xaf::NUMERIC AS observed_value,
            b._raw_payload AS raw_payload
        FROM silver.subscribers s
        JOIN bronze.subscribers b ON b.bronze_id = s.bronze_id
        WHERE b._raw_payload ? '_synthetic_anomaly'
          AND (p_bronze_loaded_after IS NULL OR b._loaded_at >= p_bronze_loaded_after)

        UNION ALL

        SELECT
            'traffic_voice'::TEXT,
            s.operator_id,
            s.service_segment,
            s.report_period,
            s.region_code,
            'silver.traffic_voice'::VARCHAR(80),
            s.silver_id,
            s.bronze_id,
            b._raw_payload -> '_synthetic_anomaly' ->> 'code',
            b._raw_payload -> '_synthetic_anomaly' -> 'changed_fields',
            (
                COALESCE(s.voice_minutes_outgoing_onnet, 0)
                + COALESCE(s.voice_minutes_outgoing_offnet, 0)
                + COALESCE(s.voice_minutes_outgoing_international, 0)
                + COALESCE(s.voice_minutes_incoming_national, 0)
                + COALESCE(s.voice_minutes_incoming_international, 0)
                + COALESCE(s.voice_minutes_fixed_local, 0)
                + COALESCE(s.voice_minutes_fixed_national, 0)
                + COALESCE(s.voice_minutes_fixed_international_outgoing, 0)
                + COALESCE(s.voice_minutes_fixed_incoming_national, 0)
                + COALESCE(s.voice_minutes_fixed_incoming_international, 0)
            )::NUMERIC,
            b._raw_payload
        FROM silver.traffic_voice s
        JOIN bronze.traffic_voice b ON b.bronze_id = s.bronze_id
        WHERE b._raw_payload ? '_synthetic_anomaly'
          AND (p_bronze_loaded_after IS NULL OR b._loaded_at >= p_bronze_loaded_after)

        UNION ALL

        SELECT
            'traffic_sms'::TEXT,
            s.operator_id,
            s.service_segment,
            s.report_period,
            s.region_code,
            'silver.traffic_sms'::VARCHAR(80),
            s.silver_id,
            s.bronze_id,
            b._raw_payload -> '_synthetic_anomaly' ->> 'code',
            b._raw_payload -> '_synthetic_anomaly' -> 'changed_fields',
            (
                COALESCE(s.sms_count_outgoing_onnet, 0)
                + COALESCE(s.sms_count_outgoing_offnet, 0)
                + COALESCE(s.sms_count_outgoing_international, 0)
                + COALESCE(s.sms_count_incoming_national, 0)
            )::NUMERIC,
            b._raw_payload
        FROM silver.traffic_sms s
        JOIN bronze.traffic_sms b ON b.bronze_id = s.bronze_id
        WHERE b._raw_payload ? '_synthetic_anomaly'
          AND (p_bronze_loaded_after IS NULL OR b._loaded_at >= p_bronze_loaded_after)

        UNION ALL

        SELECT
            'traffic_internet'::TEXT,
            s.operator_id,
            s.service_segment,
            s.report_period,
            s.region_code,
            'silver.traffic_internet'::VARCHAR(80),
            s.silver_id,
            s.bronze_id,
            b._raw_payload -> '_synthetic_anomaly' ->> 'code',
            b._raw_payload -> '_synthetic_anomaly' -> 'changed_fields',
            (
                COALESCE(s.data_consumed_mb_2g, 0)
                + COALESCE(s.data_consumed_mb_3g, 0)
                + COALESCE(s.data_consumed_mb_4g, 0)
                + COALESCE(s.data_consumed_mb_5g, 0)
                + COALESCE(s.data_consumed_mb_fiber, 0)
                + COALESCE(s.data_consumed_mb_adsl, 0)
                + COALESCE(s.data_consumed_mb_fixed_wireless, 0)
            )::NUMERIC,
            b._raw_payload
        FROM silver.traffic_internet s
        JOIN bronze.traffic_internet b ON b.bronze_id = s.bronze_id
        WHERE b._raw_payload ? '_synthetic_anomaly'
          AND (p_bronze_loaded_after IS NULL OR b._loaded_at >= p_bronze_loaded_after)

        UNION ALL

        SELECT
            'qos'::TEXT,
            s.operator_id,
            s.service_segment,
            s.report_period,
            s.region_code,
            'silver.qos'::VARCHAR(80),
            s.silver_id,
            s.bronze_id,
            b._raw_payload -> '_synthetic_anomaly' ->> 'code',
            b._raw_payload -> '_synthetic_anomaly' -> 'changed_fields',
            COALESCE(s.network_availability_pct, s.qos_related_complaints::NUMERIC),
            b._raw_payload
        FROM silver.qos s
        JOIN bronze.qos b ON b.bronze_id = s.bronze_id
        WHERE b._raw_payload ? '_synthetic_anomaly'
          AND (p_bronze_loaded_after IS NULL OR b._loaded_at >= p_bronze_loaded_after)

        UNION ALL

        SELECT
            'revenue'::TEXT,
            s.operator_id,
            s.service_segment,
            s.report_period,
            NULL::VARCHAR(8) AS region_code,
            'silver.revenue'::VARCHAR(80),
            s.silver_id,
            s.bronze_id,
            b._raw_payload -> '_synthetic_anomaly' ->> 'code',
            b._raw_payload -> '_synthetic_anomaly' -> 'changed_fields',
            s.total_revenue_xaf::NUMERIC,
            b._raw_payload
        FROM silver.revenue s
        JOIN bronze.revenue b ON b.bronze_id = s.bronze_id
        WHERE b._raw_payload ? '_synthetic_anomaly'
          AND (p_bronze_loaded_after IS NULL OR b._loaded_at >= p_bronze_loaded_after)
    ), normalized AS (
        SELECT
            md5(domain || ':' || bronze_id::TEXT || ':' || COALESCE(anomaly_code, 'unknown')) AS event_fingerprint,
            domain,
            CASE
                WHEN anomaly_code IN ('active_exceeds_total', 'component_sum_mismatch', 'usf_rate_high') THEN 'critical'
                WHEN anomaly_code IN ('qos_perfect_report', 'qos_degradation', 'subscriber_spike', 'arpu_spike') THEN 'warning'
                ELSE 'warning'
            END AS severity,
            COALESCE(anomaly_code, 'synthetic_anomaly') AS event_code,
            'Synthetic anomaly marker detected and retained in silver for monitoring.' AS event_message,
            'synthetic_anomaly_marker'::VARCHAR(120) AS detection_rule,
            operator_id,
            service_segment,
            report_period,
            region_code,
            source_table,
            source_id,
            bronze_id,
            CASE
                WHEN anomaly_code = 'arpu_spike' THEN 'arpu_xaf'
                WHEN anomaly_code = 'complaint_spike' THEN 'qos_related_complaints'
                WHEN anomaly_code = 'qos_perfect_report' THEN 'network_availability_pct'
                WHEN anomaly_code IN ('voice_traffic_spike', 'sms_traffic_spike', 'internet_traffic_spike') THEN 'traffic_volume'
                ELSE NULL
            END AS metric_name,
            observed_value,
            NULL::NUMERIC(22, 6) AS expected_min,
            NULL::NUMERIC(22, 6) AS expected_max,
            jsonb_build_object(
                'source', 'synthetic_injection',
                'anomaly_code', anomaly_code,
                'changed_fields', COALESCE(changed_fields, '[]'::jsonb),
                'raw_payload', raw_payload
            ) AS metadata
        FROM anomaly_rows
    ), upserted AS (
        INSERT INTO silver.data_quality_events (
            event_fingerprint,
            domain,
            severity,
            event_code,
            event_message,
            detection_rule,
            operator_id,
            service_segment,
            report_period,
            region_code,
            source_table,
            source_id,
            bronze_id,
            metric_name,
            observed_value,
            expected_min,
            expected_max,
            status,
            detected_by_run_id,
            metadata
        )
        SELECT
            event_fingerprint,
            domain,
            severity,
            event_code,
            event_message,
            detection_rule,
            operator_id,
            service_segment,
            report_period,
            region_code,
            source_table,
            source_id,
            bronze_id,
            metric_name,
            observed_value,
            expected_min,
            expected_max,
            'open',
            p_run_id,
            metadata
        FROM normalized
        ON CONFLICT (event_fingerprint)
        DO UPDATE SET
            severity = EXCLUDED.severity,
            event_message = EXCLUDED.event_message,
            detection_rule = EXCLUDED.detection_rule,
            operator_id = EXCLUDED.operator_id,
            service_segment = EXCLUDED.service_segment,
            report_period = EXCLUDED.report_period,
            region_code = EXCLUDED.region_code,
            source_table = EXCLUDED.source_table,
            source_id = EXCLUDED.source_id,
            bronze_id = EXCLUDED.bronze_id,
            metric_name = EXCLUDED.metric_name,
            observed_value = EXCLUDED.observed_value,
            expected_min = EXCLUDED.expected_min,
            expected_max = EXCLUDED.expected_max,
            detected_by_run_id = EXCLUDED.detected_by_run_id,
            metadata = EXCLUDED.metadata,
            detected_at = NOW(),
            status = CASE
                WHEN silver.data_quality_events.status = 'resolved' THEN 'open'
                ELSE silver.data_quality_events.status
            END
        RETURNING 1
    )
    SELECT COUNT(*) INTO v_events FROM upserted;

    RETURN v_events;
END;
$$;

COMMENT ON FUNCTION silver.capture_suspicious_anomaly_events IS
'Capture synthetic suspicious anomalies that passed silver validation into silver.data_quality_events for monitoring dashboards and alerts.';
