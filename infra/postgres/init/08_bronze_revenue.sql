-- ============================================================================
-- 08_bronze_revenue.sql
-- Raw revenue submissions broken out by service line and direction.
--
-- The component breakdown follows ARPCE-style reporting taxonomy. Voice and
-- SMS revenues split outgoing (subscriber pays) from incoming (interconnection
-- termination). Internet revenue splits by technology generation, with
-- additional lines for value-added services and other revenue.
--
-- The total_revenue_xaf column is the operator-provided sum. Silver-layer
-- validation cross-checks: components must equal total within tolerance.
-- ============================================================================

CREATE TABLE bronze.revenue (
    bronze_id                                   UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),

    source_submission_id                        TEXT,
    operator_id                                 VARCHAR(10),
    report_period                               VARCHAR(7),

    -- Voice outgoing revenue (subscribers paying for calls placed).
    revenue_voice_outgoing_onnet_xaf            BIGINT,
    revenue_voice_outgoing_offnet_xaf           BIGINT,
    revenue_voice_outgoing_international_xaf    BIGINT,

    -- Voice incoming revenue (interconnection termination fees).
    revenue_voice_incoming_national_xaf         BIGINT,
    revenue_voice_incoming_international_xaf    BIGINT,

    -- SMS revenue.
    revenue_sms_outgoing_onnet_xaf              BIGINT,
    revenue_sms_outgoing_offnet_xaf             BIGINT,
    revenue_sms_outgoing_international_xaf      BIGINT,
    revenue_sms_incoming_xaf                    BIGINT,

    -- Mobile internet revenue by technology.
    revenue_internet_2g_xaf                     BIGINT,
    revenue_internet_3g_xaf                     BIGINT,
    revenue_internet_4g_xaf                     BIGINT,
    revenue_internet_5g_xaf                     BIGINT,

    -- Other revenue lines.
    revenue_value_added_services_xaf            BIGINT,
    revenue_other_xaf                           BIGINT,

    -- Operator-provided totals.
    total_revenue_xaf                           BIGINT,
    usf_contribution_xaf                        BIGINT,

    submitted_at                                TIMESTAMPTZ,

    _source_file                                TEXT            NOT NULL,
    _source_line                                INTEGER         NOT NULL,
    _loaded_at                                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    _loaded_by_run_id                           UUID            NOT NULL,
    _raw_payload                                JSONB           NOT NULL
);

CREATE INDEX idx_bronze_revenue_operator_period
    ON bronze.revenue (operator_id, report_period);

CREATE INDEX idx_bronze_revenue_loaded_at
    ON bronze.revenue (_loaded_at);

CREATE INDEX idx_bronze_revenue_run
    ON bronze.revenue (_loaded_by_run_id);

COMMENT ON TABLE bronze.revenue IS
'Operator revenue broken out into service-line components plus totals. Source of truth for ARPU calculations and Universal Service Fund contribution tracking.';

COMMENT ON COLUMN bronze.revenue.usf_contribution_xaf IS
'Universal Service Fund contribution. Typically 1-3% of total revenue, depending on regulatory framework.';

COMMENT ON COLUMN bronze.revenue.total_revenue_xaf IS
'Operator-provided total. Silver-layer validation verifies this equals the sum of component revenue lines within tolerance.';
