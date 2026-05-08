-- ============================================================================
-- 12_silver_validation_subscribers.sql
-- Validation function for silver subscriber data.
--
-- Reads bronze.subscribers, applies reference and business-rule validation,
-- then writes clean rows to silver.subscribers and invalid rows to
-- silver.subscribers_rejections.
--
-- This function is idempotent. Re-running it updates existing silver rows and
-- refreshes existing rejection records instead of duplicating them.
-- ============================================================================

CREATE OR REPLACE FUNCTION silver.validate_subscribers(
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
        FROM bronze.subscribers b
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
                          AND b.service_segment NOT IN ('mobile', 'fixed_voice', 'fixed_broadband', 'postal', 'satellite')
                     THEN 'unknown_service_segment' END,
                CASE WHEN op.operator_id IS NOT NULL
                          AND b.service_segment IS NOT NULL
                          AND NOT (b.service_segment = ANY(op.service_segments))
                     THEN 'segment_not_licensed' END,
                CASE WHEN b.service_category IS NULL THEN 'missing_service_category' END,
                CASE WHEN b.service_category IS NOT NULL
                          AND b.service_category NOT IN ('mobile_telephony', 'mobile_internet', 'fixed_voice', 'fixed_broadband')
                     THEN 'unknown_service_category' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.service_category NOT IN ('mobile_telephony', 'mobile_internet')
                     THEN 'service_category_mismatch_mobile' END,
                CASE WHEN b.service_segment = 'fixed_voice'
                          AND b.service_category <> 'fixed_voice'
                     THEN 'service_category_mismatch_fixed_voice' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.service_category <> 'fixed_broadband'
                     THEN 'service_category_mismatch_fixed_broadband' END,
                CASE WHEN b.payment_type IS NULL THEN 'missing_payment_type' END,
                CASE WHEN b.payment_type IS NOT NULL
                          AND b.payment_type NOT IN ('prepaid', 'postpaid')
                     THEN 'unknown_payment_type' END,
                CASE WHEN b.total_subscribers IS NULL THEN 'missing_total_subscribers' END,
                CASE WHEN b.total_subscribers < 0 THEN 'negative_subscribers' END,
                CASE WHEN b.active_subscribers_30d IS NULL THEN 'missing_active_subscribers_30d' END,
                CASE WHEN b.active_subscribers_30d < 0 THEN 'negative_active' END,
                CASE WHEN b.total_subscribers IS NOT NULL
                          AND b.active_subscribers_30d IS NOT NULL
                          AND b.active_subscribers_30d > b.total_subscribers * 1.05
                     THEN 'active_exceeds_total' END,
                CASE WHEN b.new_activations IS NULL THEN 'missing_new_activations' END,
                CASE WHEN b.new_activations < 0 THEN 'negative_activations' END,
                CASE WHEN b.churn_count IS NULL THEN 'missing_churn_count' END,
                CASE WHEN b.churn_count < 0 THEN 'negative_churn' END,
                CASE WHEN b.arpu_xaf IS NULL THEN 'missing_arpu' END,
                CASE WHEN b.arpu_xaf < 0 THEN 'negative_arpu' END,
                CASE WHEN b.arpu_xaf > 50000 THEN 'arpu_implausibly_high' END,
                CASE WHEN b.service_category = 'mobile_internet'
                          AND b.technology_generation IS NULL
                     THEN 'missing_tech_generation_for_internet' END,
                CASE WHEN b.service_category = 'mobile_internet'
                          AND b.technology_generation IS NOT NULL
                          AND b.technology_generation NOT IN ('2G', '3G', '4G', '5G')
                     THEN 'unknown_technology_generation' END,
                CASE WHEN b.service_category IS NOT NULL
                          AND b.service_category <> 'mobile_internet'
                          AND b.technology_generation IS NOT NULL
                     THEN 'tech_generation_on_non_internet' END,
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
        INSERT INTO silver.subscribers (
            bronze_id,
            operator_id,
            report_period,
            region_code,
            service_segment,
            service_category,
            payment_type,
            technology_generation,
            total_subscribers,
            active_subscribers_30d,
            new_activations,
            churn_count,
            arpu_xaf,
            period_start_date,
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
            service_category,
            payment_type,
            technology_generation,
            total_subscribers,
            active_subscribers_30d,
            new_activations,
            churn_count,
            arpu_xaf,
            TO_DATE(report_period || '-01', 'YYYY-MM-DD'),
            submitted_at,
            _loaded_at,
            p_run_id
        FROM valid_rows
        ON CONFLICT (
            operator_id,
            report_period,
            region_code,
            service_segment,
            service_category,
            payment_type,
            technology_generation
        )
        DO UPDATE SET
            bronze_id = EXCLUDED.bronze_id,
            total_subscribers = EXCLUDED.total_subscribers,
            active_subscribers_30d = EXCLUDED.active_subscribers_30d,
            new_activations = EXCLUDED.new_activations,
            churn_count = EXCLUDED.churn_count,
            arpu_xaf = EXCLUDED.arpu_xaf,
            period_start_date = EXCLUDED.period_start_date,
            submitted_at = EXCLUDED.submitted_at,
            bronze_loaded_at = EXCLUDED.bronze_loaded_at,
            validated_by_run_id = EXCLUDED.validated_by_run_id,
            silver_loaded_at = NOW()
        RETURNING 1
    ),
    upsert_rejected AS (
        INSERT INTO silver.subscribers_rejections (
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

COMMENT ON FUNCTION silver.validate_subscribers IS
'Validate bronze.subscribers against reference data and subscriber business rules. Writes valid rows to silver.subscribers and invalid rows to silver.subscribers_rejections.';
