-- ============================================================================
-- 011_silver_revenue.sql
-- Silver layer for operator revenue.
--
-- Revenue is reported nationally per operator and service segment. Silver
-- stores every component line, computes component totals, and preserves the
-- arithmetic delta against the operator-provided total.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.revenue (
    silver_id                                   UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                                   UUID            NOT NULL UNIQUE,

    -- Business keys.
    operator_id                                 VARCHAR(10)     NOT NULL,
    report_period                               VARCHAR(7)      NOT NULL,
    service_segment                             VARCHAR(30)     NOT NULL,

    -- Mobile voice revenue.
    revenue_voice_outgoing_onnet_xaf            BIGINT          CHECK (revenue_voice_outgoing_onnet_xaf IS NULL OR revenue_voice_outgoing_onnet_xaf >= 0),
    revenue_voice_outgoing_offnet_xaf           BIGINT          CHECK (revenue_voice_outgoing_offnet_xaf IS NULL OR revenue_voice_outgoing_offnet_xaf >= 0),
    revenue_voice_outgoing_international_xaf    BIGINT          CHECK (revenue_voice_outgoing_international_xaf IS NULL OR revenue_voice_outgoing_international_xaf >= 0),
    revenue_voice_incoming_national_xaf         BIGINT          CHECK (revenue_voice_incoming_national_xaf IS NULL OR revenue_voice_incoming_national_xaf >= 0),
    revenue_voice_incoming_international_xaf    BIGINT          CHECK (revenue_voice_incoming_international_xaf IS NULL OR revenue_voice_incoming_international_xaf >= 0),

    -- Mobile SMS revenue.
    revenue_sms_outgoing_onnet_xaf              BIGINT          CHECK (revenue_sms_outgoing_onnet_xaf IS NULL OR revenue_sms_outgoing_onnet_xaf >= 0),
    revenue_sms_outgoing_offnet_xaf             BIGINT          CHECK (revenue_sms_outgoing_offnet_xaf IS NULL OR revenue_sms_outgoing_offnet_xaf >= 0),
    revenue_sms_outgoing_international_xaf      BIGINT          CHECK (revenue_sms_outgoing_international_xaf IS NULL OR revenue_sms_outgoing_international_xaf >= 0),
    revenue_sms_incoming_xaf                    BIGINT          CHECK (revenue_sms_incoming_xaf IS NULL OR revenue_sms_incoming_xaf >= 0),

    -- Mobile internet revenue.
    revenue_internet_2g_xaf                     BIGINT          CHECK (revenue_internet_2g_xaf IS NULL OR revenue_internet_2g_xaf >= 0),
    revenue_internet_3g_xaf                     BIGINT          CHECK (revenue_internet_3g_xaf IS NULL OR revenue_internet_3g_xaf >= 0),
    revenue_internet_4g_xaf                     BIGINT          CHECK (revenue_internet_4g_xaf IS NULL OR revenue_internet_4g_xaf >= 0),
    revenue_internet_5g_xaf                     BIGINT          CHECK (revenue_internet_5g_xaf IS NULL OR revenue_internet_5g_xaf >= 0),

    -- Fixed segment revenue.
    revenue_fixed_voice_subscription_xaf        BIGINT          CHECK (revenue_fixed_voice_subscription_xaf IS NULL OR revenue_fixed_voice_subscription_xaf >= 0),
    revenue_fixed_voice_usage_xaf               BIGINT          CHECK (revenue_fixed_voice_usage_xaf IS NULL OR revenue_fixed_voice_usage_xaf >= 0),
    revenue_fixed_broadband_subscription_xaf    BIGINT          CHECK (revenue_fixed_broadband_subscription_xaf IS NULL OR revenue_fixed_broadband_subscription_xaf >= 0),
    revenue_fixed_broadband_usage_xaf           BIGINT          CHECK (revenue_fixed_broadband_usage_xaf IS NULL OR revenue_fixed_broadband_usage_xaf >= 0),
    revenue_equipment_rental_xaf                BIGINT          CHECK (revenue_equipment_rental_xaf IS NULL OR revenue_equipment_rental_xaf >= 0),

    -- Shared revenue lines.
    revenue_value_added_services_xaf            BIGINT          CHECK (revenue_value_added_services_xaf IS NULL OR revenue_value_added_services_xaf >= 0),
    revenue_other_xaf                           BIGINT          CHECK (revenue_other_xaf IS NULL OR revenue_other_xaf >= 0),

    -- Operator-provided total and silver-derived arithmetic checks.
    total_revenue_xaf                           BIGINT          NOT NULL CHECK (total_revenue_xaf >= 0),
    components_sum_xaf                          BIGINT          NOT NULL CHECK (components_sum_xaf >= 0),
    sum_check_delta_xaf                         BIGINT          NOT NULL,
    usf_contribution_xaf                        BIGINT          CHECK (usf_contribution_xaf IS NULL OR usf_contribution_xaf >= 0),
    usf_contribution_rate_pct                   NUMERIC(6, 3),

    -- Lineage.
    period_start_date                           DATE            NOT NULL,
    submitted_at                                TIMESTAMPTZ     NOT NULL,
    bronze_loaded_at                            TIMESTAMPTZ     NOT NULL,
    validated_by_run_id                         UUID,
    silver_loaded_at                            TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_silver_revenue_business_key
        UNIQUE (operator_id, report_period, service_segment),

    CONSTRAINT fk_silver_revenue_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.revenue (bronze_id),

    CONSTRAINT fk_silver_revenue_run
        FOREIGN KEY (validated_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_silver_revenue_segment_period
    ON silver.revenue (service_segment, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_revenue_operator_period
    ON silver.revenue (operator_id, report_period);

CREATE INDEX IF NOT EXISTS idx_silver_revenue_run
    ON silver.revenue (validated_by_run_id);

COMMENT ON TABLE silver.revenue IS
'Validated operator revenue by service segment. Includes every component line plus derived component sum, total delta, and USF contribution rate.';

COMMENT ON COLUMN silver.revenue.components_sum_xaf IS
'Sum of all populated revenue component lines. Should equal total_revenue_xaf within tolerance.';

COMMENT ON COLUMN silver.revenue.sum_check_delta_xaf IS
'Difference between total_revenue_xaf and components_sum_xaf. Negative means total is below components; positive means total is above components.';

COMMENT ON COLUMN silver.revenue.usf_contribution_rate_pct IS
'Computed as usf_contribution_xaf / total_revenue_xaf * 100.';

CREATE TABLE IF NOT EXISTS silver.revenue_rejections (
    rejection_id                                UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bronze_id                                   UUID            NOT NULL UNIQUE,
    rejection_reason                            TEXT            NOT NULL,
    rejection_codes                             TEXT[]          NOT NULL,
    rejected_at                                 TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    rejected_by_run_id                          UUID,

    CONSTRAINT fk_revenue_rejections_bronze
        FOREIGN KEY (bronze_id) REFERENCES bronze.revenue (bronze_id),

    CONSTRAINT fk_revenue_rejections_run
        FOREIGN KEY (rejected_by_run_id) REFERENCES audit.pipeline_runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_revenue_rejections_codes
    ON silver.revenue_rejections USING GIN (rejection_codes);

CREATE INDEX IF NOT EXISTS idx_revenue_rejections_run
    ON silver.revenue_rejections (rejected_by_run_id);

COMMENT ON TABLE silver.revenue_rejections IS
'Bronze revenue rows that failed silver validation, with machine-readable reason codes.';
