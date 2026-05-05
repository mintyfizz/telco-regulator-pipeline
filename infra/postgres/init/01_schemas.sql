-- ============================================================================
-- 01_schemas.sql
-- Creates the medallion architecture schemas and required extensions.
-- Runs first because subsequent files reference these schemas and extensions.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS audit;

COMMENT ON SCHEMA bronze IS 'Raw operator submissions, captured exactly as received with audit metadata.';
COMMENT ON SCHEMA silver IS 'Cleaned, validated, deduplicated data ready for analytical queries.';
COMMENT ON SCHEMA gold IS 'Business-ready dimensional models for dashboards and reporting.';
COMMENT ON SCHEMA audit IS 'Pipeline run history, ingestion metadata, validation results.';

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";