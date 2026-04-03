-- ============================================================================
-- ZarishSphere FHIR R5 Engine — PostgreSQL 18.3 Schema
-- ============================================================================
-- Design decisions:
--   - JSONB for complete FHIR resources (flexible, GIN-indexed, no ORM mapping)
--   - Separate search_params table for fast, indexed FHIR parameter queries
--   - Row-Level Security (RLS) enforces tenant_id isolation at DB layer
--   - Async I/O (PostgreSQL 18 feature) enabled on connection pool
--   - TimescaleDB hypertable for time-series observations
--   - Immutable history table for audit trail
-- Governance: ADR-0003 (PostgreSQL as only database)
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy name search
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;  -- TimescaleDB 2.25

-- ============================================================================
-- Core FHIR resource table
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhir_resources (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type   TEXT        NOT NULL,
    fhir_id         TEXT        NOT NULL,
    version_id      INTEGER     NOT NULL DEFAULT 1,
    resource        JSONB       NOT NULL,           -- Complete FHIR R5 resource JSON
    tenant_id       TEXT        NOT NULL,           -- Multi-tenancy (ADR-0003)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,                    -- Soft delete (GDPR)
    CONSTRAINT uq_fhir_resource UNIQUE (resource_type, fhir_id, tenant_id)
);

-- GIN index for JSONB FHIR search (supports @>, @?, jsonpath operators)
CREATE INDEX IF NOT EXISTS idx_fhir_resources_gin
    ON fhir_resources USING GIN (resource);

-- B-tree composite index for type+tenant queries (primary lookup pattern)
CREATE INDEX IF NOT EXISTS idx_fhir_resources_type_tenant
    ON fhir_resources (resource_type, tenant_id)
    WHERE deleted_at IS NULL;

-- Trigram index on patient name for fuzzy search
CREATE INDEX IF NOT EXISTS idx_fhir_patient_name_trgm
    ON fhir_resources USING GIN (
        (resource->>'resourceType'),
        (resource->'name'->0->>'family') gin_trgm_ops
    );

-- B-tree index on updated_at for history queries
CREATE INDEX IF NOT EXISTS idx_fhir_resources_updated
    ON fhir_resources (updated_at DESC)
    WHERE deleted_at IS NULL;

-- ============================================================================
-- FHIR history table (immutable audit of all versions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhir_history (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id     UUID        REFERENCES fhir_resources(id) ON DELETE SET NULL,
    resource_type   TEXT        NOT NULL,
    fhir_id         TEXT        NOT NULL,
    version_id      INTEGER     NOT NULL,
    tenant_id       TEXT        NOT NULL,
    resource        JSONB       NOT NULL,
    operation       TEXT        NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by     TEXT,                           -- User/system ref
    client_id       TEXT,                           -- SMART client_id
    ip_address      INET
);

CREATE INDEX IF NOT EXISTS idx_fhir_history_resource
    ON fhir_history (resource_type, fhir_id, tenant_id, version_id DESC);

-- ============================================================================
-- FHIR search parameters table (pre-extracted for fast indexed lookup)
-- Populated by triggers on fhir_resources INSERT/UPDATE
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhir_search_params (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id   UUID        NOT NULL REFERENCES fhir_resources(id) ON DELETE CASCADE,
    resource_type TEXT        NOT NULL,
    tenant_id     TEXT        NOT NULL,
    param_name    TEXT        NOT NULL,  -- e.g. "name", "birthdate", "identifier"
    param_type    TEXT        NOT NULL,  -- string | token | date | reference | quantity | uri | composite
    value_string  TEXT,                 -- For string and token searches
    value_token_system TEXT,            -- For token searches (system part)
    value_token_code   TEXT,            -- For token searches (code part)
    value_date    TIMESTAMPTZ,          -- For date searches
    value_number  NUMERIC(18,6),        -- For quantity searches
    value_ref_type TEXT,                -- For reference searches (resource type)
    value_ref_id   TEXT,                -- For reference searches (resource ID)
    value_uri     TEXT                  -- For URI searches
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

-- ============================================================================
-- FHIR AuditEvent table (time-partitioned — heavy write volume)
-- Uses TimescaleDB 2.25 for efficient time-series storage
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhir_audit_events (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       TEXT        NOT NULL,
    action          CHAR(1)     NOT NULL,           -- C R U D E
    resource_type   TEXT,
    resource_id     TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    outcome_code    TEXT        NOT NULL DEFAULT '0',
    agent_ref       TEXT,                           -- Practitioner/xxx
    agent_name      TEXT,
    client_id       TEXT,                           -- SMART client_id
    ip_address      INET,
    smart_scopes    TEXT[],
    event_json      JSONB       NOT NULL            -- Full FHIR AuditEvent JSON
);

-- Convert to TimescaleDB hypertable (partition by recorded_at, 1-week chunks)
SELECT create_hypertable('fhir_audit_events', 'recorded_at',
    chunk_time_interval => INTERVAL '1 week',
    if_not_exists => TRUE
);

-- Retain audit data for 7 years (HIPAA requirement)
SELECT add_retention_policy('fhir_audit_events',
    INTERVAL '7 years',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_audit_tenant_recorded
    ON fhir_audit_events (tenant_id, recorded_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_resource
    ON fhir_audit_events (resource_type, resource_id, tenant_id)
    WHERE resource_type IS NOT NULL;

-- ============================================================================
-- FHIR Subscriptions table (FHIR R5 topic-based subscriptions)
-- Backed by NATS JetStream for delivery (ADR-0004)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhir_subscriptions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    fhir_id         TEXT        NOT NULL UNIQUE,
    tenant_id       TEXT        NOT NULL,
    topic_url       TEXT        NOT NULL,           -- SubscriptionTopic URL
    status          TEXT        NOT NULL DEFAULT 'requested',
    channel_type    TEXT        NOT NULL,           -- rest-hook | websocket | email | message
    channel_endpoint TEXT,                          -- Webhook URL for rest-hook
    channel_payload TEXT        DEFAULT 'application/fhir+json',
    filter_criteria JSONB,                          -- FHIR subscription filter params
    heartbeat_period INTEGER    DEFAULT 300,        -- seconds
    timeout         INTEGER     DEFAULT 60,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_event_at   TIMESTAMPTZ,
    error_count     INTEGER     NOT NULL DEFAULT 0,
    subscription_json JSONB     NOT NULL            -- Full FHIR Subscription resource
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant_topic
    ON fhir_subscriptions (tenant_id, topic_url, status);

-- ============================================================================
-- FHIR CapabilityStatement cache (updated on server restart)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fhir_capability_statement (
    id              SERIAL      PRIMARY KEY,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    statement       JSONB       NOT NULL
);

-- ============================================================================
-- Row-Level Security (RLS) — tenant isolation (ADR-0003)
-- Every query from application layer MUST set app.tenant_id.
-- This is the last line of defense against cross-tenant data leakage.
-- ============================================================================

ALTER TABLE fhir_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_search_params ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE fhir_subscriptions ENABLE ROW LEVEL SECURITY;

-- Application role (used by connection pool)
DO $$ BEGIN
    CREATE ROLE zs_fhir_app;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON fhir_resources TO zs_fhir_app;
GRANT SELECT, INSERT ON fhir_history TO zs_fhir_app;
GRANT SELECT, INSERT, DELETE ON fhir_search_params TO zs_fhir_app;
GRANT SELECT, INSERT ON fhir_audit_events TO zs_fhir_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON fhir_subscriptions TO zs_fhir_app;

-- RLS policies: app sets SET LOCAL app.tenant_id = 'org:program:site'
CREATE POLICY tenant_isolation_fhir_resources ON fhir_resources
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_fhir_history ON fhir_history
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_search_params ON fhir_search_params
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_audit ON fhir_audit_events
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

CREATE POLICY tenant_isolation_subscriptions ON fhir_subscriptions
    FOR ALL TO zs_fhir_app
    USING (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================================
-- Vital signs hypertable for TimescaleDB 2.25 time-series analytics
-- ============================================================================
CREATE TABLE IF NOT EXISTS observation_timeseries (
    id              UUID        NOT NULL DEFAULT gen_random_uuid(),
    tenant_id       TEXT        NOT NULL,
    patient_id      TEXT        NOT NULL,
    encounter_id    TEXT,
    loinc_code      TEXT        NOT NULL,           -- LOINC observation code
    value_quantity  NUMERIC(12,4),
    value_unit      TEXT,
    value_ucum      TEXT,
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fhir_id         TEXT        NOT NULL            -- Link back to fhir_resources
);

SELECT create_hypertable('observation_timeseries', 'recorded_at',
    chunk_time_interval => INTERVAL '1 month',
    if_not_exists => TRUE
);

CREATE INDEX IF NOT EXISTS idx_obs_ts_patient_loinc
    ON observation_timeseries (tenant_id, patient_id, loinc_code, recorded_at DESC);

-- ============================================================================
-- Terminology cache table (ICD-11, SNOMED, LOINC, CIEL, RxNorm, CVX)
-- Populated by zs-svc-terminology
-- ============================================================================
CREATE TABLE IF NOT EXISTS terminology_concepts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    code_system     TEXT        NOT NULL,           -- ICD-11 | SNOMED | LOINC | CIEL | RxNorm | CVX
    code            TEXT        NOT NULL,
    display         TEXT        NOT NULL,
    display_bn      TEXT,                           -- Bengali
    display_my      TEXT,                           -- Burmese
    display_ur      TEXT,                           -- Urdu
    definition      TEXT,
    parent_code     TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_terminology UNIQUE (code_system, code)
);

CREATE INDEX IF NOT EXISTS idx_terminology_code
    ON terminology_concepts (code_system, code)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_terminology_display_trgm
    ON terminology_concepts USING GIN (display gin_trgm_ops)
    WHERE is_active = TRUE;
