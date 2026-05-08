-- ============================================================================
-- 010_silver_validation_qos.sql
-- Validation function for silver Quality of Service data.
-- ============================================================================

CREATE OR REPLACE FUNCTION silver.validate_qos(
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
        FROM bronze.qos b
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
                          AND b.service_segment NOT IN ('mobile', 'fixed_voice', 'fixed_broadband')
                     THEN 'qos_unsupported_segment' END,
                CASE WHEN op.operator_id IS NOT NULL
                          AND b.service_segment IS NOT NULL
                          AND NOT (b.service_segment = ANY(op.service_segments))
                     THEN 'segment_not_licensed' END,

                -- Methodology and granularity.
                CASE WHEN b.measurement_methodology IS NULL THEN 'missing_methodology' END,
                CASE WHEN b.measurement_methodology IS NOT NULL
                          AND b.measurement_methodology NOT IN (
                              'operator_self_reported',
                              'regulator_audit',
                              'independent_drive_test'
                          )
                     THEN 'unknown_methodology' END,
                CASE WHEN b.period_type IS NULL THEN 'missing_period_type' END,
                CASE WHEN b.period_type IS NOT NULL
                          AND b.period_type NOT IN ('monthly', 'weekly', 'daily', 'realtime')
                     THEN 'unknown_period_type' END,

                -- Mobile QoS rows require mobile/radio metrics and no fixed metrics.
                CASE WHEN b.service_segment = 'mobile'
                          AND b.network_availability_pct IS NULL
                     THEN 'mobile_missing_availability' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.call_drop_rate_pct IS NULL
                     THEN 'mobile_missing_drop_rate' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.call_setup_success_rate_pct IS NULL
                     THEN 'mobile_missing_setup_success' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.avg_data_throughput_mbps_4g IS NULL
                     THEN 'mobile_missing_4g_throughput' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.avg_data_throughput_mbps_3g IS NULL
                     THEN 'mobile_missing_3g_throughput' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND b.avg_latency_ms IS NULL
                     THEN 'mobile_missing_latency' END,
                CASE WHEN b.service_segment = 'mobile'
                          AND (
                              b.avg_fixed_download_mbps IS NOT NULL
                              OR b.avg_fixed_upload_mbps IS NOT NULL
                              OR b.avg_packet_loss_pct IS NOT NULL
                              OR b.fixed_broadband_coverage_pct IS NOT NULL
                              OR b.fixed_service_repair_time_hours IS NOT NULL
                          )
                     THEN 'mobile_has_fixed_qos_columns' END,

                -- Fixed voice uses availability and repair time, not broadband throughput.
                CASE WHEN b.service_segment = 'fixed_voice'
                          AND b.network_availability_pct IS NULL
                     THEN 'fixed_voice_missing_availability' END,
                CASE WHEN b.service_segment = 'fixed_voice'
                          AND b.fixed_service_repair_time_hours IS NULL
                     THEN 'fixed_voice_missing_repair_time' END,
                CASE WHEN b.service_segment = 'fixed_voice'
                          AND (
                              b.call_drop_rate_pct IS NOT NULL
                              OR b.call_setup_success_rate_pct IS NOT NULL
                              OR b.avg_data_throughput_mbps_4g IS NOT NULL
                              OR b.avg_data_throughput_mbps_3g IS NOT NULL
                              OR b.avg_latency_ms IS NOT NULL
                              OR b.population_coverage_pct_4g IS NOT NULL
                              OR b.population_coverage_pct_3g IS NOT NULL
                              OR b.population_coverage_pct_2g IS NOT NULL
                              OR b.avg_fixed_download_mbps IS NOT NULL
                              OR b.avg_fixed_upload_mbps IS NOT NULL
                              OR b.avg_packet_loss_pct IS NOT NULL
                              OR b.fixed_broadband_coverage_pct IS NOT NULL
                          )
                     THEN 'fixed_voice_has_unrelated_qos_columns' END,

                -- Fixed broadband uses fixed throughput/latency/coverage metrics.
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.network_availability_pct IS NULL
                     THEN 'fixed_broadband_missing_availability' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.avg_fixed_download_mbps IS NULL
                     THEN 'fixed_broadband_missing_download' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.avg_fixed_upload_mbps IS NULL
                     THEN 'fixed_broadband_missing_upload' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.avg_latency_ms IS NULL
                     THEN 'fixed_broadband_missing_latency' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.avg_packet_loss_pct IS NULL
                     THEN 'fixed_broadband_missing_packet_loss' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.fixed_broadband_coverage_pct IS NULL
                     THEN 'fixed_broadband_missing_coverage' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND b.fixed_service_repair_time_hours IS NULL
                     THEN 'fixed_broadband_missing_repair_time' END,
                CASE WHEN b.service_segment = 'fixed_broadband'
                          AND (
                              b.call_drop_rate_pct IS NOT NULL
                              OR b.call_setup_success_rate_pct IS NOT NULL
                              OR b.avg_data_throughput_mbps_4g IS NOT NULL
                              OR b.avg_data_throughput_mbps_3g IS NOT NULL
                              OR b.population_coverage_pct_4g IS NOT NULL
                              OR b.population_coverage_pct_3g IS NOT NULL
                              OR b.population_coverage_pct_2g IS NOT NULL
                          )
                     THEN 'fixed_broadband_has_mobile_qos_columns' END,

                -- Universal range and missing-value checks.
                CASE WHEN b.network_availability_pct < 0 OR b.network_availability_pct > 100
                     THEN 'availability_out_of_range' END,
                CASE WHEN b.call_drop_rate_pct < 0 OR b.call_drop_rate_pct > 100
                     THEN 'drop_rate_out_of_range' END,
                CASE WHEN b.call_setup_success_rate_pct < 0 OR b.call_setup_success_rate_pct > 100
                     THEN 'setup_success_out_of_range' END,
                CASE WHEN b.avg_data_throughput_mbps_4g < 0 THEN 'negative_4g_throughput' END,
                CASE WHEN b.avg_data_throughput_mbps_3g < 0 THEN 'negative_3g_throughput' END,
                CASE WHEN b.avg_latency_ms < 0 OR b.avg_latency_ms > 5000
                     THEN 'latency_implausible' END,
                CASE WHEN b.population_coverage_pct_4g < 0 OR b.population_coverage_pct_4g > 100
                     THEN 'coverage_4g_out_of_range' END,
                CASE WHEN b.population_coverage_pct_3g < 0 OR b.population_coverage_pct_3g > 100
                     THEN 'coverage_3g_out_of_range' END,
                CASE WHEN b.population_coverage_pct_2g < 0 OR b.population_coverage_pct_2g > 100
                     THEN 'coverage_2g_out_of_range' END,
                CASE WHEN b.avg_fixed_download_mbps < 0 THEN 'negative_fixed_download' END,
                CASE WHEN b.avg_fixed_upload_mbps < 0 THEN 'negative_fixed_upload' END,
                CASE WHEN b.avg_packet_loss_pct < 0 OR b.avg_packet_loss_pct > 100
                     THEN 'packet_loss_out_of_range' END,
                CASE WHEN b.fixed_broadband_coverage_pct < 0 OR b.fixed_broadband_coverage_pct > 100
                     THEN 'fixed_coverage_out_of_range' END,
                CASE WHEN b.fixed_service_repair_time_hours < 0
                     THEN 'negative_repair_time' END,
                CASE WHEN b.qos_related_complaints IS NULL THEN 'missing_complaints' END,
                CASE WHEN b.qos_related_complaints < 0 THEN 'negative_complaints' END,
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
        INSERT INTO silver.qos (
            bronze_id,
            operator_id,
            report_period,
            region_code,
            service_segment,
            measurement_methodology,
            period_type,
            network_availability_pct,
            call_drop_rate_pct,
            call_setup_success_rate_pct,
            avg_data_throughput_mbps_4g,
            avg_data_throughput_mbps_3g,
            avg_latency_ms,
            population_coverage_pct_4g,
            population_coverage_pct_3g,
            population_coverage_pct_2g,
            qos_related_complaints,
            avg_fixed_download_mbps,
            avg_fixed_upload_mbps,
            avg_packet_loss_pct,
            fixed_broadband_coverage_pct,
            fixed_service_repair_time_hours,
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
            measurement_methodology,
            period_type,
            network_availability_pct,
            call_drop_rate_pct,
            call_setup_success_rate_pct,
            avg_data_throughput_mbps_4g,
            avg_data_throughput_mbps_3g,
            avg_latency_ms,
            population_coverage_pct_4g,
            population_coverage_pct_3g,
            population_coverage_pct_2g,
            qos_related_complaints,
            avg_fixed_download_mbps,
            avg_fixed_upload_mbps,
            avg_packet_loss_pct,
            fixed_broadband_coverage_pct,
            fixed_service_repair_time_hours,
            TO_DATE(report_period || '-01', 'YYYY-MM-DD'),
            submitted_at,
            _loaded_at,
            p_run_id
        FROM valid_rows
        ON CONFLICT (operator_id, report_period, region_code, service_segment)
        DO UPDATE SET
            bronze_id = EXCLUDED.bronze_id,
            measurement_methodology = EXCLUDED.measurement_methodology,
            period_type = EXCLUDED.period_type,
            network_availability_pct = EXCLUDED.network_availability_pct,
            call_drop_rate_pct = EXCLUDED.call_drop_rate_pct,
            call_setup_success_rate_pct = EXCLUDED.call_setup_success_rate_pct,
            avg_data_throughput_mbps_4g = EXCLUDED.avg_data_throughput_mbps_4g,
            avg_data_throughput_mbps_3g = EXCLUDED.avg_data_throughput_mbps_3g,
            avg_latency_ms = EXCLUDED.avg_latency_ms,
            population_coverage_pct_4g = EXCLUDED.population_coverage_pct_4g,
            population_coverage_pct_3g = EXCLUDED.population_coverage_pct_3g,
            population_coverage_pct_2g = EXCLUDED.population_coverage_pct_2g,
            qos_related_complaints = EXCLUDED.qos_related_complaints,
            avg_fixed_download_mbps = EXCLUDED.avg_fixed_download_mbps,
            avg_fixed_upload_mbps = EXCLUDED.avg_fixed_upload_mbps,
            avg_packet_loss_pct = EXCLUDED.avg_packet_loss_pct,
            fixed_broadband_coverage_pct = EXCLUDED.fixed_broadband_coverage_pct,
            fixed_service_repair_time_hours = EXCLUDED.fixed_service_repair_time_hours,
            period_start_date = EXCLUDED.period_start_date,
            submitted_at = EXCLUDED.submitted_at,
            bronze_loaded_at = EXCLUDED.bronze_loaded_at,
            validated_by_run_id = EXCLUDED.validated_by_run_id,
            silver_loaded_at = NOW()
        RETURNING 1
    ),
    upsert_rejected AS (
        INSERT INTO silver.qos_rejections (
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

COMMENT ON FUNCTION silver.validate_qos IS
'Validate bronze.qos against reference data, QoS range checks, and segment-specific metric requirements. Writes clean rows to silver.qos and invalid rows to silver.qos_rejections.';
