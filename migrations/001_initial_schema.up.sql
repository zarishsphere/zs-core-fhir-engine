-- Migration: 001_initial_schema.up
-- ZarishSphere FHIR R5 Engine — PostgreSQL 18.3 initial schema
-- golang-migrate format: one file per migration, idempotent (IF NOT EXISTS)
-- Run with: make migrate-up  OR  golang-migrate up

-- This migration creates the complete FHIR R5 storage schema.
-- See internal/storage/schema.sql for the full annotated version.

BEGIN;

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Core FHIR resources table
CREATE TABLE IF NOT EXISTS fhir_resources (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type TEXT        NOT NULL,
    fhir_id       TEXT        NOT NULL,
    version_id    INTEGER     NOT NULL DEFAULT 1,
    resource      JSONB       NOT NULL,
    tenant_id     TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at    TIMESTAMPTZ,
    CONSTRAINT uq_fhir_resource UNIQUE (resource_type, fhir_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_fhir_resources_gin
    ON fhir_resources USING GIN (resource);

CREATE INDEX IF NOT EXISTS idx_fhir_resources_type_tenant
    ON fhir_resources (resource_type, tenant_id)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_fhir_resources_updated
    ON fhir_resources (updated_at DESC)
    WHERE deleted_at IS NULL;

-- Trigram index for patient name search
CREATE INDEX IF NOT EXISTS idx_fhir_patient_name_trgm
    ON fhir_resources USING GIN ((resource->'name'->0->>'family') gin_trgm_ops)
    WHERE resource_type = 'Patient';

-- FHIR history (immutable)
CREATE TABLE IF NOT EXISTS fhir_history (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id   UUID        REFERENCES fhir_resources(id) ON DELETE SET NULL,
    resource_type TEXT        NOT NULL,
    fhir_id       TEXT        NOT NULL,
    version_id    INTEGER     NOT NULL,
    tenant_id     TEXT        NOT NULL,
    resource      JSONB       NOT NULL,
    operation     TEXT        NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by   TEXT,
    client_id     TEXT,
    ip_address    INET
);

CREATE INDEX IF NOT EXISTS idx_fhir_history_resource
    ON fhir_history (resource_type, fhir_id, tenant_id, version_id DESC);

-- FHIR search parameters
CREATE TABLE IF NOT EXISTS fhir_search_params (
    id                UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id       UUID    NOT NULL REFERENCES fhir_resources(id) ON DELETE CASCADE,
    resource_type     TEXT    NOT NULL,
    tenant_id         TEXT    NOT NULL,
    param_name        TEXT    NOT NULL,
    param_type        TEXT    NOT NULL,
    value_string      TEXT,
    value_token_system TEXT,
    value_token_code  TEXT,
    value_date        TIMESTAMPTZ,
    value_number      NUMERIC(18,6),
    value_ref_type    TEXT,
    value_ref_id      TEXT,
    value_uri         TEXT
);

CREATE INDEX IF NOT EXISTS idx_search_string
    ON fhir_search_params (resource_type, tenant_id, param_name, value_string)
    WHERE param_type = 'string';

CREATE INDEX IF NOT EXISTS idx_search_token
    ON fhir_search_params (resource_type, tenant_id, param_name, value_token_system, value_token_code)
    WHERE param_type = 'token';

CREATE INDEX IF NOT EXISTS idx_search_date
    ON fhir_search_params (resource_type, tenant_id, param_name, value_date)
    WHERE param_type = 'date';

CREATE INDEX IF NOT EXISTS idx_search_reference
    ON fhir_search_params (resource_type, tenant_id, param_name, value_ref_type, value_ref_id)
    WHERE param_type = 'reference';

CREATE INDEX IF NOT EXISTS idx_search_number
    ON fhir_search_params (resource_type, tenant_id, param_name, value_number)
    WHERE param_type = 'quantity';

-- FHIR Subscriptions (NATS-backed delivery)
CREATE TABLE IF NOT EXISTS fhir_subscriptions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    fhir_id             TEXT        NOT NULL UNIQUE,
    tenant_id           TEXT        NOT NULL,
    topic_url           TEXT        NOT NULL,
    status              TEXT        NOT NULL DEFAULT 'requested',
    channel_type        TEXT        NOT NULL DEFAULT 'rest-hook',
    channel_endpoint    TEXT,
    channel_payload     TEXT        DEFAULT 'application/fhir+json',
    filter_criteria     JSONB,
    heartbeat_period    INTEGER     DEFAULT 300,
    timeout             INTEGER     DEFAULT 60,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event_at       TIMESTAMPTZ,
    error_count         INTEGER     NOT NULL DEFAULT 0,
    subscription_json   JSONB       NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant_topic
    ON fhir_subscriptions (tenant_id, topic_url, status);

-- Terminology cache
CREATE TABLE IF NOT EXISTS terminology_concepts (
    id          UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    code_system TEXT    NOT NULL,
    code        TEXT    NOT NULL,
    display     TEXT    NOT NULL,
    display_bn  TEXT,
    display_my  TEXT,
    display_ur  TEXT,
    definition  TEXT,
    parent_code TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_terminology UNIQUE (code_system, code)
);

CREATE INDEX IF NOT EXISTS idx_terminology_code
    ON terminology_concepts (code_system, code) WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_terminology_display_trgm
    ON terminology_concepts USING GIN (display gin_trgm_ops) WHERE is_active = TRUE;

-- Row-Level Security
ALTER TABLE fhir_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_search_params ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_subscriptions ENABLE ROW LEVEL SECURITY;

-- Application role
DO $$ BEGIN
    CREATE ROLE zs_fhir_app;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON fhir_resources, fhir_subscriptions TO zs_fhir_app;
GRANT SELECT, INSERT ON fhir_history, terminology_concepts TO zs_fhir_app;
GRANT SELECT, INSERT, DELETE ON fhir_search_params TO zs_fhir_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO zs_fhir_app;

CREATE POLICY tenant_isolation_resources ON fhir_resources
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_history ON fhir_history
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_search ON fhir_search_params
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_subscriptions ON fhir_subscriptions
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

COMMIT;
