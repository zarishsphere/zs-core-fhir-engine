-- Migration: 002_timescaledb_hypertables.down
-- Removes TimescaleDB hypertables and reverts to plain tables.
-- WARNING: This drops all time-series data. Use only in development/testing.
BEGIN;
DROP TABLE IF EXISTS fhir_audit_events CASCADE;
DROP TABLE IF EXISTS observation_timeseries CASCADE;
COMMIT;
