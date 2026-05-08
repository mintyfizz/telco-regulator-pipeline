-- ============================================================================
-- 008_silver_validation_traffic_internet.sql
-- Validation function for silver internet/data traffic.
-- ============================================================================

CREATE OR REPLACE FUNCTION silver.validate_traffic_internet(
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
        FROM bronze.traffic_internet b
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
                CASE WHEN b.service_segment IS NOT NULL
                          AND b.service_segment NOT IN ('mobile', 'fixed_broadband')
                     THEN 'internet_unsupported_segment' END,
                CASE WHEN op.operator_id IS NOT NULL
                          AND b.service_segment IS NOT NULL
                          AND NOT (b.service_segment = ANY(op.service_segments))
                     THEN 'segment_not_licensed' END,

                -- Mobile internet rows use generation columns; fixed access columns must be empty/zero.
                CASE WHEN b.service_segment = 'mobile'
                          AND b.data_consumed_mb_2g IS NULL
                     THEN 'mobile_missing_2g_data' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.data_consumed_mb_3g IS NULL
                     THEN 'mobile_missing_3g_data' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.data_consumed_mb_4g IS NULL
                     THEN 'mobile_missing_4g_data' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND (
                              COALESCE(b.data_consumed_mb_fiber, 0) <> 0
                              OR COALESCE(b.data_consumed_mb_adsl, 0) <> 0
                              OR COALESCE(b.data_consumed_mb_fixed_wireless, 0) <> 0
                          )
                     THEN 'mobile_has_fixed_broadband_data' END,

                -- Fixed broadband rows use access-technology columns; mobile generation columns must be empty/zero.
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.data_consumed_mb_fiber IS NULL
                     THEN 'fixed_broadband_missing_fiber_data' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.data_consumed_mb_adsl IS NULL
                     THEN 'fixed_broadband_missing_adsl_data' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.data_consumed_mb_fixed_wireless IS NULL
                     THEN 'fixed_broadband_missing_fixed_wireless_data' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND (
                              COALESCE(b.data_consumed_mb_2g, 0) <> 0
                              OR COALESCE(b.data_consumed_mb_3g, 0) <> 0
                              OR COALESCE(b.data_consumed_mb_4g, 0) <> 0
                              OR COALESCE(b.data_consumed_mb_5g, 0) <> 0
                          )
                     THEN 'fixed_broadband_has_mobile_generation_data' END,

                CASE WHEN b.data_consumed_mb_2g < 0 THEN 'negative_2g_data' END,
                CASE WHEN b.data_consumed_mb_3g < 0 THEN 'negative_3g_data' END,
                CASE WHEN b.data_consumed_mb_4g < 0 THEN 'negative_4g_data' END,
                CASE WHEN b.data_consumed_mb_5g < 0 THEN 'negative_5g_data' END,
                CASE WHEN b.data_consumed_mb_fiber < 0 THEN 'negative_fiber_data' END,
                CASE WHEN b.data_consumed_mb_adsl < 0 THEN 'negative_adsl_data' END,
                CASE WHEN b.data_consumed_mb_fixed_wireless < 0 THEN 'negative_fixed_wireless_data' END,
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
        INSERT INTO silver.traffic_internet (
            bronze_id,
            operator_id,
            report_period,
            region_code,
            service_segment,
            data_consumed_mb_2g,
            data_consumed_mb_3g,
            data_consumed_mb_4g,
            data_consumed_mb_5g,
            data_consumed_mb_fiber,
            data_consumed_mb_adsl,
            data_consumed_mb_fixed_wireless,
            period_start_date,
            total_data_consumed_mb,
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
            data_consumed_mb_2g,
            data_consumed_mb_3g,
            data_consumed_mb_4g,
            data_consumed_mb_5g,
            data_consumed_mb_fiber,
            data_consumed_mb_adsl,
            data_consumed_mb_fixed_wireless,
            TO_DATE(report_period || '-01', 'YYYY-MM-DD'),
            COALESCE(data_consumed_mb_2g, 0)
                + COALESCE(data_consumed_mb_3g, 0)
                + COALESCE(data_consumed_mb_4g, 0)
                + COALESCE(data_consumed_mb_5g, 0)
                + COALESCE(data_consumed_mb_fiber, 0)
                + COALESCE(data_consumed_mb_adsl, 0)
                + COALESCE(data_consumed_mb_fixed_wireless, 0),
            submitted_at,
            _loaded_at,
            p_run_id
        FROM valid_rows
        ON CONFLICT (operator_id, report_period, region_code, service_segment)
        DO UPDATE SET
            bronze_id = EXCLUDED.bronze_id,
            data_consumed_mb_2g = EXCLUDED.data_consumed_mb_2g,
            data_consumed_mb_3g = EXCLUDED.data_consumed_mb_3g,
            data_consumed_mb_4g = EXCLUDED.data_consumed_mb_4g,
            data_consumed_mb_5g = EXCLUDED.data_consumed_mb_5g,
            data_consumed_mb_fiber = EXCLUDED.data_consumed_mb_fiber,
            data_consumed_mb_adsl = EXCLUDED.data_consumed_mb_adsl,
            data_consumed_mb_fixed_wireless = EXCLUDED.data_consumed_mb_fixed_wireless,
            period_start_date = EXCLUDED.period_start_date,
            total_data_consumed_mb = EXCLUDED.total_data_consumed_mb,
            submitted_at = EXCLUDED.submitted_at,
            bronze_loaded_at = EXCLUDED.bronze_loaded_at,
            validated_by_run_id = EXCLUDED.validated_by_run_id,
            silver_loaded_at = NOW()
        RETURNING 1
    ),
    upsert_rejected AS (
        INSERT INTO silver.traffic_internet_rejections (
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

COMMENT ON FUNCTION silver.validate_traffic_internet IS
'Validate bronze.traffic_internet against reference data and segment-specific internet traffic rules. Writes clean rows to silver.traffic_internet and invalid rows to silver.traffic_internet_rejections.';
