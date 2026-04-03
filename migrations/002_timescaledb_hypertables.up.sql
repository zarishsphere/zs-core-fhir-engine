-- Migration: 002_timescaledb_hypertables.up
-- Adds TimescaleDB 2.25 hypertables for time-series clinical data.
-- Requires timescaledb extension (included in timescale/timescaledb:2.25-pg18 image).
-- Governance: ADR-0003 (PostgreSQL + TimescaleDB as only database)

BEGIN;

-- Observation time-series (vitals trends, lab trends)
-- Powers clinical dashboards and trend analytics
CREATE TABLE IF NOT EXISTS observation_timeseries (
    id           UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant_id    TEXT        NOT NULL,
    patient_id   TEXT        NOT NULL,
    encounter_id TEXT,
    loinc_code   TEXT        NOT NULL,
    value_qty    NUMERIC(12,4),
    value_unit   TEXT,
    value_ucum   TEXT,
    value_bool   BOOLEAN,
    value_text   TEXT,
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fhir_id      TEXT        NOT NULL
);

-- Convert to TimescaleDB hypertable partitioned by time (1-month chunks)
SELECT create_hypertable(
    'observation_timeseries', 'recorded_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_obs_ts_patient
    ON observation_timeseries (tenant_id, patient_id, loinc_code, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_obs_ts_encounter
    ON observation_timeseries (tenant_id, encounter_id, recorded_at DESC)
    WHERE encounter_id IS NOT NULL;

-- Audit events time-series (heavy write, time-range queries)
CREATE TABLE IF NOT EXISTS fhir_audit_events (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       TEXT        NOT NULL,
    action          CHAR(1)     NOT NULL,
    resource_type   TEXT,
    resource_id     TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome_code    TEXT        NOT NULL DEFAULT '0',
    agent_ref       TEXT,
    agent_name      TEXT,
    client_id       TEXT,
    ip_address      INET,
    smart_scopes    TEXT[],
    event_json      JSONB       NOT NULL
);

SELECT create_hypertable(
    'fhir_audit_events', 'recorded_at',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- 7-year retention policy (HIPAA requirement)
SELECT add_retention_policy(
    'fhir_audit_events',
    INTERVAL '7 years',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant
    ON fhir_audit_events (tenant_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_resource
    ON fhir_audit_events (resource_type, resource_id, tenant_id)
    WHERE resource_type IS NOT NULL;

-- RLS for audit events
ALTER TABLE fhir_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE observation_timeseries ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT ON fhir_audit_events, observation_timeseries TO zs_fhir_app;

CREATE POLICY tenant_isolation_audit ON fhir_audit_events
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_obs_ts ON observation_timeseries
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

COMMIT;
