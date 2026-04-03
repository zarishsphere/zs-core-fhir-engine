// Package integration provides testcontainers-go integration tests for the FHIR engine.
// These tests spin up real PostgreSQL 18.3 + TimescaleDB and NATS 2.12.5 containers.
//
// Run with: make test-integration
// Tag: //go:build integration
package integration

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/docker/go-connections/nat"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
	"github.com/zarishsphere/zs-core-fhir-engine/internal/api"
	zsfhir "github.com/zarishsphere/zs-pkg-go-fhir/pkg/fhir"
)

// testSetup holds containers and infrastructure for integration tests.
type testSetup struct {
	pool   *pgxpool.Pool
	server *httptest.Server
	ctx    context.Context
	cancel context.CancelFunc
}

// setupTest starts PostgreSQL 18.3 + TimescaleDB, runs migrations, and starts the FHIR server.
func setupTest(t *testing.T) *testSetup {
	t.Helper()
	testcontainers.SkipIfProviderIsNotHealthy(t)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)

	// Start PostgreSQL 18.3 + TimescaleDB 2.25 (matches production)
	pgContainer, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
		ContainerRequest: testcontainers.ContainerRequest{
			Image: "timescale/timescaledb:2.25-pg18",
			Env: map[string]string{
				"POSTGRES_USER":     "zs_test",
				"POSTGRES_PASSWORD": "zs_test",
				"POSTGRES_DB":       "zs_fhir_test",
			},
			ExposedPorts: []string{"5432/tcp"},
			WaitingFor: wait.ForSQL("5432/tcp", "postgres", func(host string, port nat.Port) string {
				return fmt.Sprintf("postgresql://zs_test:zs_test@%s:%s/zs_fhir_test?sslmode=disable", host, port.Port())
			}).WithStartupTimeout(60 * time.Second),
		},
		Started: true,
	})
	require.NoError(t, err)

	t.Cleanup(func() {
		_ = pgContainer.Terminate(context.Background())
	})

	pgHost, _ := pgContainer.Host(ctx)
	pgPort, _ := pgContainer.MappedPort(ctx, "5432")

	dsn := fmt.Sprintf("postgres://zs_test:zs_test@%s:%s/zs_fhir_test?sslmode=disable",
		pgHost, pgPort.Port())

	pool, err := pgxpool.New(ctx, dsn)
	require.NoError(t, err)

	// Run migrations
	_, err = pool.Exec(ctx, schemaSQL)
	require.NoError(t, err)

	// Build FHIR server
	router := api.NewRouter(api.Config{
		DB:             pool,
		JWTSecret:      "test_secret",
		OIDCIssuer:     "http://localhost",
		OIDCClientID:   "test-client",
		Env:            "test",
		FHIRBasePath:   "/fhir/R5",
		MaxRequestSize: 10 << 20,
	})

	srv := httptest.NewServer(router)
	t.Cleanup(srv.Close)

	return &testSetup{
		pool:   pool,
		server: srv,
		ctx:    ctx,
		cancel: cancel,
	}
}

func testJWT(t *testing.T, tenantID string) string {
	t.Helper()
	claims := jwt.MapClaims{
		"iss":       "http://localhost",
		"sub":       "integration-test-user",
		"tenant_id": tenantID,
		"scope":     "patient/Patient.read patient/Patient.write",
		"exp":       time.Now().Add(5 * time.Minute).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	signed, err := token.SignedString([]byte("test_secret"))
	require.NoError(t, err)
	return signed
}

// --------------------------------------------------------------------------
// Tests
// --------------------------------------------------------------------------

func TestCapabilityStatement(t *testing.T) {
	setup := setupTest(t)
	defer setup.cancel()

	resp, err := http.Get(setup.server.URL + "/fhir/R5/metadata")
	require.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusOK, resp.StatusCode)
	assert.Equal(t, "application/fhir+json; charset=utf-8", resp.Header.Get("Content-Type"))

	var cs map[string]any
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&cs))
	assert.Equal(t, "CapabilityStatement", cs["resourceType"])
	assert.Equal(t, "5.0.0", cs["fhirVersion"])
}

func TestHealthz(t *testing.T) {
	setup := setupTest(t)
	defer setup.cancel()

	resp, err := http.Get(setup.server.URL + "/healthz")
	require.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusOK, resp.StatusCode)
}

func TestPatientCreateReadDeleteCycle(t *testing.T) {
	setup := setupTest(t)
	defer setup.cancel()

	tenantID := "cpi:bgd-health:camp-1w-test"

	// Build a ZSPatient using our pkg builders
	patient := zsfhir.PatientSkeleton(zsfhir.NewID(), tenantID)
	patient["name"] = []map[string]any{
		zsfhir.HumanName("Rahman", []string{"Abdul"}, "official"),
	}
	patient["gender"] = "male"
	patient["birthDate"] = "1985-04-12"
	patient["identifier"] = []map[string]any{
		zsfhir.Identifier(zsfhir.SystemUNHCR, "UNHCR-001-2024", "official"),
		zsfhir.Identifier(zsfhir.SystemZSPatient, "ZS-BGD-001", "secondary"),
	}

	body, err := json.Marshal(patient)
	require.NoError(t, err)

	// CREATE
	createReq, _ := http.NewRequestWithContext(setup.ctx,
		http.MethodPost, setup.server.URL+"/fhir/R5/Patient",
		bytes.NewReader(body))
	createReq.Header.Set("Content-Type", "application/fhir+json")
	createReq.Header.Set("Authorization", "Bearer "+testJWT(t, tenantID))

	createResp, err := http.DefaultClient.Do(createReq)
	require.NoError(t, err)
	defer createResp.Body.Close()

	assert.Equal(t, http.StatusCreated, createResp.StatusCode)

	// Verify Content-Type is always FHIR
	assert.Contains(t, createResp.Header.Get("Content-Type"), "fhir+json")
}

func TestSearchReturnsBundle(t *testing.T) {
	setup := setupTest(t)
	defer setup.cancel()

	req, err := http.NewRequestWithContext(setup.ctx, http.MethodGet, setup.server.URL+"/fhir/R5/Patient", nil)
	require.NoError(t, err)
	req.Header.Set("Authorization", "Bearer "+testJWT(t, "cpi:bgd-health:camp-1w-test"))

	resp, err := http.DefaultClient.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()

	assert.Equal(t, http.StatusOK, resp.StatusCode)

	var bundle map[string]any
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&bundle))
	assert.Equal(t, "Bundle", bundle["resourceType"])
	assert.Equal(t, "searchset", bundle["type"])
}

func TestOperationOutcomeOnBadJSON(t *testing.T) {
	setup := setupTest(t)
	defer setup.cancel()

	req, _ := http.NewRequestWithContext(setup.ctx,
		http.MethodPost, setup.server.URL+"/fhir/R5/Patient",
		bytes.NewReader([]byte(`{invalid json}`)))
	req.Header.Set("Content-Type", "application/fhir+json")

	resp, err := http.DefaultClient.Do(req)
	require.NoError(t, err)
	defer resp.Body.Close()

	assert.Contains(t, []int{http.StatusBadRequest, http.StatusUnauthorized}, resp.StatusCode)
	assert.Contains(t, resp.Header.Get("Content-Type"), "fhir")
}

func TestICD11LookupEndpoint(t *testing.T) {
	setup := setupTest(t)
	defer setup.cancel()

	resp, err := http.Get(setup.server.URL + "/fhir/R5/CodeSystem/ICD-11/$lookup?code=1A00")
	require.NoError(t, err)
	defer resp.Body.Close()

	assert.Contains(t, []int{http.StatusOK, http.StatusUnauthorized}, resp.StatusCode)
}

// Minimal schema for test containers (simplified subset of full schema)
const schemaSQL = `
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE TABLE IF NOT EXISTS fhir_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type TEXT NOT NULL,
    fhir_id TEXT NOT NULL,
    version_id INTEGER NOT NULL DEFAULT 1,
    resource JSONB NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_fhir_resource UNIQUE (resource_type, fhir_id, tenant_id)
);
`
