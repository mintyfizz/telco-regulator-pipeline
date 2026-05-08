-- ============================================================================
-- 006_silver_validation_traffic_sms.sql
-- Validation function for silver SMS traffic data.
-- ============================================================================

CREATE OR REPLACE FUNCTION silver.validate_traffic_sms(
    p_run_id UUID DEFAULT NULL,
    p_bronze_loaded_after TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
    rows_processed BIGINT,
    rows_validated BIGINT,
    rows_rejected BIGINT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_processed BIGINT := 0;
    v_validated BIGINT := 0;
    v_rejected BIGINT := 0;
BEGIN
    WITH bronze_to_validate AS (
        SELECT b.*
        FROM bronze.traffic_sms b
        WHERE p_bronze_loaded_after IS NULL
           OR b._loaded_at >= p_bronze_loaded_after
    ),
    validation_results AS (
        SELECT
            b.*,
            ARRAY_REMOVE(ARRAY[
                CASE WHEN b.operator_id IS NULL THEN 'missing_operator' END,
                CASE WHEN op.operator_id IS NULL THEN 'unknown_operator' END,
                CASE WHEN b.report_period IS NULL THEN 'missing_report_period' END,
                CASE WHEN b.report_period IS NOT NULL
                          AND b.report_period !~ '^\d{4}-(0[1-9]|1[0-2])$'
                     THEN 'invalid_period_format' END,
                CASE WHEN b.report_period ~ '^\d{4}-(0[1-9]|1[0-2])$'
                          AND TO_DATE(b.report_period || '-01', 'YYYY-MM-DD') < DATE '2018-01-01'
                     THEN 'period_too_old' END,
                CASE WHEN b.report_period ~ '^\d{4}-(0[1-9]|1[0-2])$'
                          AND TO_DATE(b.report_period || '-01', 'YYYY-MM-DD') > (CURRENT_DATE + INTERVAL '1 month')
                     THEN 'period_in_future' END,
                CASE WHEN b.region_code IS NULL THEN 'missing_region' END,
                CASE WHEN reg.region_code IS NULL THEN 'unknown_region' END,
                CASE WHEN b.service_segment IS NULL THEN 'missing_service_segment' END,
                CASE WHEN b.service_segment <> 'mobile' THEN 'sms_only_supported_for_mobile' END,
                CASE WHEN op.operator_id IS NOT NULL
                          AND b.service_segment IS NOT NULL
                          AND NOT (b.service_segment = ANY(op.service_segments))
                     THEN 'segment_not_licensed' END,
                CASE WHEN b.sms_count_outgoing_onnet IS NULL THEN 'missing_outgoing_onnet' END,
                CASE WHEN b.sms_count_outgoing_offnet IS NULL THEN 'missing_outgoing_offnet' END,
                CASE WHEN b.sms_count_outgoing_international IS NULL THEN 'missing_outgoing_international' END,
                CASE WHEN b.sms_count_incoming_national IS NULL THEN 'missing_incoming_national' END,
                CASE WHEN b.sms_count_outgoing_onnet < 0 THEN 'negative_outgoing_onnet' END,
                CASE WHEN b.sms_count_outgoing_offnet < 0 THEN 'negative_outgoing_offnet' END,
                CASE WHEN b.sms_count_outgoing_international < 0 THEN 'negative_outgoing_international' END,
                CASE WHEN b.sms_count_incoming_national < 0 THEN 'negative_incoming_national' END,
                CASE WHEN b.submitted_at IS NULL THEN 'missing_submitted_at' END
            ], NULL) AS rejection_codes
        FROM bronze_to_validate b
        LEFT JOIN silver.operators op ON op.operator_id = b.operator_id
        LEFT JOIN silver.regions reg ON reg.region_code = b.region_code
    ),
    valid_rows AS (
        SELECT *
        FROM validation_results
        WHERE COALESCE(ARRAY_LENGTH(rejection_codes, 1), 0) = 0
    ),
    rejected_rows AS (
        SELECT *
        FROM validation_results
        WHERE COALESCE(ARRAY_LENGTH(rejection_codes, 1), 0) > 0
    ),
    insert_valid AS (
        INSERT INTO silver.traffic_sms (
            bronze_id,
            operator_id,
            report_period,
            region_code,
            service_segment,
            sms_count_outgoing_onnet,
            sms_count_outgoing_offnet,
            sms_count_outgoing_international,
            sms_count_incoming_national,
            period_start_date,
            total_outgoing_sms,
            submitted_at,
            bronze_loaded_at,
            validated_by_run_id
        )
        SELECT
            bronze_id,
            operator_id,
            report_period,
            region_code,
            service_segment,
            sms_count_outgoing_onnet,
            sms_count_outgoing_offnet,
            sms_count_outgoing_international,
            sms_count_incoming_national,
            TO_DATE(report_period || '-01', 'YYYY-MM-DD'),
            COALESCE(sms_count_outgoing_onnet, 0)
                + COALESCE(sms_count_outgoing_offnet, 0)
                + COALESCE(sms_count_outgoing_international, 0),
            submitted_at,
            _loaded_at,
            p_run_id
        FROM valid_rows
        ON CONFLICT (operator_id, report_period, region_code, service_segment)
        DO UPDATE SET
            bronze_id = EXCLUDED.bronze_id,
            sms_count_outgoing_onnet = EXCLUDED.sms_count_outgoing_onnet,
            sms_count_outgoing_offnet = EXCLUDED.sms_count_outgoing_offnet,
            sms_count_outgoing_international = EXCLUDED.sms_count_outgoing_international,
            sms_count_incoming_national = EXCLUDED.sms_count_incoming_national,
            period_start_date = EXCLUDED.period_start_date,
            total_outgoing_sms = EXCLUDED.total_outgoing_sms,
            submitted_at = EXCLUDED.submitted_at,
            bronze_loaded_at = EXCLUDED.bronze_loaded_at,
            validated_by_run_id = EXCLUDED.validated_by_run_id,
            silver_loaded_at = NOW()
        RETURNING 1
    ),
    upsert_rejected AS (
        INSERT INTO silver.traffic_sms_rejections (
            bronze_id,
            rejection_reason,
            rejection_codes,
            rejected_by_run_id
        )
        SELECT
            bronze_id,
            'Validation failed: ' || ARRAY_TO_STRING(rejection_codes, ', '),
            rejection_codes,
            p_run_id
        FROM rejected_rows
        ON CONFLICT (bronze_id)
        DO UPDATE SET
            rejection_reason = EXCLUDED.rejection_reason,
            rejection_codes = EXCLUDED.rejection_codes,
            rejected_by_run_id = EXCLUDED.rejected_by_run_id,
            rejected_at = NOW()
        RETURNING 1
    )
    SELECT
        (SELECT COUNT(*) FROM validation_results),
        (SELECT COUNT(*) FROM insert_valid),
        (SELECT COUNT(*) FROM upsert_rejected)
    INTO v_processed, v_validated, v_rejected;

    RETURN QUERY SELECT v_processed, v_validated, v_rejected;
END;
$$;

COMMENT ON FUNCTION silver.validate_traffic_sms IS
'Validate bronze.traffic_sms against reference data and mobile-only SMS traffic rules. Writes clean rows to silver.traffic_sms and invalid rows to silver.traffic_sms_rejections.';
