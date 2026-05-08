-- ============================================================================
-- 013_silver_run_all_validations.sql
-- Orchestrator function for all silver validation domains.
-- ============================================================================

CREATE OR REPLACE FUNCTION silver.run_all_validations(
    p_run_id UUID DEFAULT NULL,
    p_bronze_loaded_after TIMESTAMPTZ DEFAULT NULL
) RETURNS TABLE (
    domain TEXT,
    rows_processed BIGINT,
    rows_validated BIGINT,
    rows_rejected BIGINT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 'subscribers'::TEXT, v.*
    FROM silver.validate_subscribers(p_run_id, p_bronze_loaded_after) AS v

    UNION ALL
    SELECT 'traffic_voice'::TEXT, v.*
    FROM silver.validate_traffic_voice(p_run_id, p_bronze_loaded_after) AS v

    UNION ALL
    SELECT 'traffic_sms'::TEXT, v.*
    FROM silver.validate_traffic_sms(p_run_id, p_bronze_loaded_after) AS v

    UNION ALL
    SELECT 'traffic_internet'::TEXT, v.*
    FROM silver.validate_traffic_internet(p_run_id, p_bronze_loaded_after) AS v

    UNION ALL
    SELECT 'qos'::TEXT, v.*
    FROM silver.validate_qos(p_run_id, p_bronze_loaded_after) AS v

    UNION ALL
    SELECT 'revenue'::TEXT, v.*
    FROM silver.validate_revenue(p_run_id, p_bronze_loaded_after) AS v;
END;
$$;

COMMENT ON FUNCTION silver.run_all_validations IS
'Run every silver validation function in domain order and return per-domain processed, validated, and rejected counts.';
