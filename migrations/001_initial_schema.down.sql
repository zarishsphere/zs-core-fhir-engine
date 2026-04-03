-- Migration: 001_initial_schema.down
-- Rolls back the initial FHIR engine schema.
-- WARNING: This drops all FHIR data. Only use in development/testing.

BEGIN;

DROP POLICY IF EXISTS tenant_isolation_subscriptions ON fhir_subscriptions;
DROP POLICY IF EXISTS tenant_isolation_search ON fhir_search_params;
DROP POLICY IF EXISTS tenant_isolation_history ON fhir_history;
DROP POLICY IF EXISTS tenant_isolation_resources ON fhir_resources;

DROP TABLE IF EXISTS terminology_concepts;
DROP TABLE IF EXISTS fhir_subscriptions;
DROP TABLE IF EXISTS fhir_search_params;
DROP TABLE IF EXISTS fhir_history;
DROP TABLE IF EXISTS fhir_resources;

COMMIT;
