-- ============================================================================
-- 012_silver_validation_revenue.sql
-- Validation function for silver revenue data.
-- ============================================================================

CREATE OR REPLACE FUNCTION silver.validate_revenue(
    p_run_id UUID DEFAULT NULL,
    p_bronze_loaded_after TIMESTAMPTZ DEFAULT NULL,
    p_sum_tolerance_pct NUMERIC DEFAULT 1.0
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
        FROM bronze.revenue b
        WHERE p_bronze_loaded_after IS NULL
           OR b._loaded_at >= p_bronze_loaded_after
    ),
    computed AS (
        SELECT
            b.*,
            COALESCE(b.revenue_voice_outgoing_onnet_xaf, 0)
                + COALESCE(b.revenue_voice_outgoing_offnet_xaf, 0)
                + COALESCE(b.revenue_voice_outgoing_international_xaf, 0)
                + COALESCE(b.revenue_voice_incoming_national_xaf, 0)
                + COALESCE(b.revenue_voice_incoming_international_xaf, 0)
                + COALESCE(b.revenue_sms_outgoing_onnet_xaf, 0)
                + COALESCE(b.revenue_sms_outgoing_offnet_xaf, 0)
                + COALESCE(b.revenue_sms_outgoing_international_xaf, 0)
                + COALESCE(b.revenue_sms_incoming_xaf, 0)
                + COALESCE(b.revenue_internet_2g_xaf, 0)
                + COALESCE(b.revenue_internet_3g_xaf, 0)
                + COALESCE(b.revenue_internet_4g_xaf, 0)
                + COALESCE(b.revenue_internet_5g_xaf, 0)
                + COALESCE(b.revenue_fixed_voice_subscription_xaf, 0)
                + COALESCE(b.revenue_fixed_voice_usage_xaf, 0)
                + COALESCE(b.revenue_fixed_broadband_subscription_xaf, 0)
                + COALESCE(b.revenue_fixed_broadband_usage_xaf, 0)
                + COALESCE(b.revenue_equipment_rental_xaf, 0)
                + COALESCE(b.revenue_value_added_services_xaf, 0)
                + COALESCE(b.revenue_other_xaf, 0) AS components_sum_xaf
        FROM bronze_to_validate b
    ),
    validation_results AS (
        SELECT
            c.*,
            c.total_revenue_xaf - c.components_sum_xaf AS sum_check_delta_xaf,
            ARRAY_REMOVE(ARRAY[
                CASE WHEN c.operator_id IS NULL THEN 'missing_operator' END,
                CASE WHEN op.operator_id IS NULL THEN 'unknown_operator' END,
                CASE WHEN c.report_period IS NULL THEN 'missing_report_period' END,
                CASE WHEN c.report_period IS NOT NULL
                          AND c.report_period !~ '^\d{4}-(0[1-9]|1[0-2])$'
                     THEN 'invalid_period_format' END,
                CASE WHEN c.report_period ~ '^\d{4}-(0[1-9]|1[0-2])$'
                          AND TO_DATE(c.report_period || '-01', 'YYYY-MM-DD') < DATE '2018-01-01'
                     THEN 'period_too_old' END,
                CASE WHEN c.report_period ~ '^\d{4}-(0[1-9]|1[0-2])$'
                          AND TO_DATE(c.report_period || '-01', 'YYYY-MM-DD') > (CURRENT_DATE + INTERVAL '1 month')
                     THEN 'period_in_future' END,
                CASE WHEN c.service_segment IS NULL THEN 'missing_service_segment' END,
                CASE WHEN c.service_segment IS NOT NULL
                          AND c.service_segment NOT IN ('mobile', 'fixed_voice', 'fixed_broadband')
                     THEN 'revenue_unsupported_segment' END,
                CASE WHEN op.operator_id IS NOT NULL
                          AND c.service_segment IS NOT NULL
                          AND NOT (c.service_segment = ANY(op.service_segments))
                     THEN 'segment_not_licensed' END,

                -- Segment-specific component population.
                CASE WHEN c.service_segment = 'mobile'
                          AND COALESCE(c.revenue_internet_4g_xaf, 0) = 0
                     THEN 'mobile_missing_4g_revenue' END,
                CASE WHEN c.service_segment = 'mobile'
                          AND (
                              COALESCE(c.revenue_fixed_voice_subscription_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_voice_usage_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_broadband_subscription_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_broadband_usage_xaf, 0) <> 0
                              OR COALESCE(c.revenue_equipment_rental_xaf, 0) <> 0
                          )
                     THEN 'mobile_has_fixed_revenue' END,
                CASE WHEN c.service_segment = 'fixed_voice'
                          AND (
                              COALESCE(c.revenue_fixed_voice_subscription_xaf, 0) = 0
                              OR COALESCE(c.revenue_fixed_voice_usage_xaf, 0) = 0
                          )
                     THEN 'fixed_voice_missing_revenue_components' END,
                CASE WHEN c.service_segment = 'fixed_voice'
                          AND (
                              COALESCE(c.revenue_voice_outgoing_onnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_outgoing_offnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_outgoing_international_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_incoming_national_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_incoming_international_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_outgoing_onnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_outgoing_offnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_outgoing_international_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_incoming_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_2g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_3g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_4g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_5g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_broadband_subscription_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_broadband_usage_xaf, 0) <> 0
                              OR COALESCE(c.revenue_value_added_services_xaf, 0) <> 0
                          )
                     THEN 'fixed_voice_has_unrelated_revenue' END,
                CASE WHEN c.service_segment = 'fixed_broadband'
                          AND (
                              COALESCE(c.revenue_fixed_broadband_subscription_xaf, 0) = 0
                              OR COALESCE(c.revenue_fixed_broadband_usage_xaf, 0) = 0
                          )
                     THEN 'fixed_broadband_missing_revenue_components' END,
                CASE WHEN c.service_segment = 'fixed_broadband'
                          AND (
                              COALESCE(c.revenue_voice_outgoing_onnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_outgoing_offnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_outgoing_international_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_incoming_national_xaf, 0) <> 0
                              OR COALESCE(c.revenue_voice_incoming_international_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_outgoing_onnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_outgoing_offnet_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_outgoing_international_xaf, 0) <> 0
                              OR COALESCE(c.revenue_sms_incoming_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_2g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_3g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_4g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_internet_5g_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_voice_subscription_xaf, 0) <> 0
                              OR COALESCE(c.revenue_fixed_voice_usage_xaf, 0) <> 0
                          )
                     THEN 'fixed_broadband_has_unrelated_revenue' END,

                -- Required totals and arithmetic.
                CASE WHEN c.total_revenue_xaf IS NULL THEN 'missing_total_revenue' END,
                CASE WHEN c.total_revenue_xaf < 0 THEN 'negative_total_revenue' END,
                CASE WHEN c.total_revenue_xaf = 0 AND c.components_sum_xaf > 0
                     THEN 'zero_total_with_components' END,
                CASE WHEN c.total_revenue_xaf > 0
                          AND ABS(c.total_revenue_xaf - c.components_sum_xaf)
                              > c.total_revenue_xaf * (p_sum_tolerance_pct / 100.0)
                     THEN 'component_sum_mismatch' END,

                -- Nonnegative component checks.
                CASE WHEN c.revenue_voice_outgoing_onnet_xaf < 0 THEN 'negative_voice_onnet' END,
                CASE WHEN c.revenue_voice_outgoing_offnet_xaf < 0 THEN 'negative_voice_offnet' END,
                CASE WHEN c.revenue_voice_outgoing_international_xaf < 0 THEN 'negative_voice_international' END,
                CASE WHEN c.revenue_voice_incoming_national_xaf < 0 THEN 'negative_voice_incoming_national' END,
                CASE WHEN c.revenue_voice_incoming_international_xaf < 0 THEN 'negative_voice_incoming_international' END,
                CASE WHEN c.revenue_sms_outgoing_onnet_xaf < 0 THEN 'negative_sms_onnet' END,
                CASE WHEN c.revenue_sms_outgoing_offnet_xaf < 0 THEN 'negative_sms_offnet' END,
                CASE WHEN c.revenue_sms_outgoing_international_xaf < 0 THEN 'negative_sms_international' END,
                CASE WHEN c.revenue_sms_incoming_xaf < 0 THEN 'negative_sms_incoming' END,
                CASE WHEN c.revenue_internet_2g_xaf < 0 THEN 'negative_internet_2g' END,
                CASE WHEN c.revenue_internet_3g_xaf < 0 THEN 'negative_internet_3g' END,
                CASE WHEN c.revenue_internet_4g_xaf < 0 THEN 'negative_internet_4g' END,
                CASE WHEN c.revenue_internet_5g_xaf < 0 THEN 'negative_internet_5g' END,
                CASE WHEN c.revenue_fixed_voice_subscription_xaf < 0 THEN 'negative_fixed_voice_subscription' END,
                CASE WHEN c.revenue_fixed_voice_usage_xaf < 0 THEN 'negative_fixed_voice_usage' END,
                CASE WHEN c.revenue_fixed_broadband_subscription_xaf < 0 THEN 'negative_fixed_broadband_subscription' END,
                CASE WHEN c.revenue_fixed_broadband_usage_xaf < 0 THEN 'negative_fixed_broadband_usage' END,
                CASE WHEN c.revenue_equipment_rental_xaf < 0 THEN 'negative_equipment_rental' END,
                CASE WHEN c.revenue_value_added_services_xaf < 0 THEN 'negative_value_added_services' END,
                CASE WHEN c.revenue_other_xaf < 0 THEN 'negative_other_revenue' END,

                -- USF contribution sanity checks.
                CASE WHEN c.usf_contribution_xaf < 0 THEN 'negative_usf_contribution' END,
                CASE WHEN c.usf_contribution_xaf IS NOT NULL
                          AND c.total_revenue_xaf > 0
                          AND (c.usf_contribution_xaf::NUMERIC / c.total_revenue_xaf::NUMERIC) > 0.10
                     THEN 'usf_rate_implausibly_high' END,
                CASE WHEN c.submitted_at IS NULL THEN 'missing_submitted_at' END
            ], NULL) AS rejection_codes
        FROM computed c
        LEFT JOIN silver.operators op ON op.operator_id = c.operator_id
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
        INSERT INTO silver.revenue (
            bronze_id,
            operator_id,
            report_period,
            service_segment,
            revenue_voice_outgoing_onnet_xaf,
            revenue_voice_outgoing_offnet_xaf,
            revenue_voice_outgoing_international_xaf,
            revenue_voice_incoming_national_xaf,
            revenue_voice_incoming_international_xaf,
            revenue_sms_outgoing_onnet_xaf,
            revenue_sms_outgoing_offnet_xaf,
            revenue_sms_outgoing_international_xaf,
            revenue_sms_incoming_xaf,
            revenue_internet_2g_xaf,
            revenue_internet_3g_xaf,
            revenue_internet_4g_xaf,
            revenue_internet_5g_xaf,
            revenue_fixed_voice_subscription_xaf,
            revenue_fixed_voice_usage_xaf,
            revenue_fixed_broadband_subscription_xaf,
            revenue_fixed_broadband_usage_xaf,
            revenue_equipment_rental_xaf,
            revenue_value_added_services_xaf,
            revenue_other_xaf,
            total_revenue_xaf,
            components_sum_xaf,
            sum_check_delta_xaf,
            usf_contribution_xaf,
            usf_contribution_rate_pct,
            period_start_date,
            submitted_at,
            bronze_loaded_at,
            validated_by_run_id
        )
        SELECT
            bronze_id,
            operator_id,
            report_period,
            service_segment,
            revenue_voice_outgoing_onnet_xaf,
            revenue_voice_outgoing_offnet_xaf,
            revenue_voice_outgoing_international_xaf,
            revenue_voice_incoming_national_xaf,
            revenue_voice_incoming_international_xaf,
            revenue_sms_outgoing_onnet_xaf,
            revenue_sms_outgoing_offnet_xaf,
            revenue_sms_outgoing_international_xaf,
            revenue_sms_incoming_xaf,
            revenue_internet_2g_xaf,
            revenue_internet_3g_xaf,
            revenue_internet_4g_xaf,
            revenue_internet_5g_xaf,
            revenue_fixed_voice_subscription_xaf,
            revenue_fixed_voice_usage_xaf,
            revenue_fixed_broadband_subscription_xaf,
            revenue_fixed_broadband_usage_xaf,
            revenue_equipment_rental_xaf,
            revenue_value_added_services_xaf,
            revenue_other_xaf,
            total_revenue_xaf,
            components_sum_xaf,
            sum_check_delta_xaf,
            usf_contribution_xaf,
            CASE WHEN total_revenue_xaf > 0 AND usf_contribution_xaf IS NOT NULL
                 THEN ROUND((usf_contribution_xaf::NUMERIC / total_revenue_xaf::NUMERIC) * 100, 3)
                 ELSE NULL END,
            TO_DATE(report_period || '-01', 'YYYY-MM-DD'),
            submitted_at,
            _loaded_at,
            p_run_id
        FROM valid_rows
        ON CONFLICT (operator_id, report_period, service_segment)
        DO UPDATE SET
            bronze_id = EXCLUDED.bronze_id,
            revenue_voice_outgoing_onnet_xaf = EXCLUDED.revenue_voice_outgoing_onnet_xaf,
            revenue_voice_outgoing_offnet_xaf = EXCLUDED.revenue_voice_outgoing_offnet_xaf,
            revenue_voice_outgoing_international_xaf = EXCLUDED.revenue_voice_outgoing_international_xaf,
            revenue_voice_incoming_national_xaf = EXCLUDED.revenue_voice_incoming_national_xaf,
            revenue_voice_incoming_international_xaf = EXCLUDED.revenue_voice_incoming_international_xaf,
            revenue_sms_outgoing_onnet_xaf = EXCLUDED.revenue_sms_outgoing_onnet_xaf,
            revenue_sms_outgoing_offnet_xaf = EXCLUDED.revenue_sms_outgoing_offnet_xaf,
            revenue_sms_outgoing_international_xaf = EXCLUDED.revenue_sms_outgoing_international_xaf,
            revenue_sms_incoming_xaf = EXCLUDED.revenue_sms_incoming_xaf,
            revenue_internet_2g_xaf = EXCLUDED.revenue_internet_2g_xaf,
            revenue_internet_3g_xaf = EXCLUDED.revenue_internet_3g_xaf,
            revenue_internet_4g_xaf = EXCLUDED.revenue_internet_4g_xaf,
            revenue_internet_5g_xaf = EXCLUDED.revenue_internet_5g_xaf,
            revenue_fixed_voice_subscription_xaf = EXCLUDED.revenue_fixed_voice_subscription_xaf,
            revenue_fixed_voice_usage_xaf = EXCLUDED.revenue_fixed_voice_usage_xaf,
            revenue_fixed_broadband_subscription_xaf = EXCLUDED.revenue_fixed_broadband_subscription_xaf,
            revenue_fixed_broadband_usage_xaf = EXCLUDED.revenue_fixed_broadband_usage_xaf,
            revenue_equipment_rental_xaf = EXCLUDED.revenue_equipment_rental_xaf,
            revenue_value_added_services_xaf = EXCLUDED.revenue_value_added_services_xaf,
            revenue_other_xaf = EXCLUDED.revenue_other_xaf,
            total_revenue_xaf = EXCLUDED.total_revenue_xaf,
            components_sum_xaf = EXCLUDED.components_sum_xaf,
            sum_check_delta_xaf = EXCLUDED.sum_check_delta_xaf,
            usf_contribution_xaf = EXCLUDED.usf_contribution_xaf,
            usf_contribution_rate_pct = EXCLUDED.usf_contribution_rate_pct,
            period_start_date = EXCLUDED.period_start_date,
            submitted_at = EXCLUDED.submitted_at,
            bronze_loaded_at = EXCLUDED.bronze_loaded_at,
            validated_by_run_id = EXCLUDED.validated_by_run_id,
            silver_loaded_at = NOW()
        RETURNING 1
    ),
    upsert_rejected AS (
        INSERT INTO silver.revenue_rejections (
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

COMMENT ON FUNCTION silver.validate_revenue IS
'Validate bronze.revenue against operator licensing, segment-specific component rules, nonnegative amounts, component-sum arithmetic, and USF contribution sanity checks.';
