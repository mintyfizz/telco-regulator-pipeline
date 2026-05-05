-- ============================================================================
-- 07_functions.sql
-- Utility functions and triggers used by silver and gold tables.
-- ============================================================================

CREATE OR REPLACE FUNCTION audit.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION audit.update_updated_at() IS
'Trigger function that auto-updates the updated_at column on row modification. Attached via CREATE TRIGGER on tables that have an updated_at column.';

CREATE TRIGGER trg_operators_updated_at
    BEFORE UPDATE ON silver.operators
    FOR EACH ROW
    EXECUTE FUNCTION audit.update_updated_at();
    