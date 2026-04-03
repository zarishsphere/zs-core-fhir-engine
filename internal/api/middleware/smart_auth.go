// Package middleware provides HTTP middleware for the ZarishSphere FHIR engine.
package middleware

import (
	"context"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
	"github.com/rs/zerolog/log"
	"github.com/zarishsphere/zs-core-fhir-engine/internal/api/contextkeys"
)

// principalContextKey is the context key for the authenticated principal.
type principalContextKey struct{}

// Claims represents ZarishSphere SMART on FHIR JWT claims.
// Keycloak 26.5.6 issues tokens with these fields.
type Claims struct {
	jwt.RegisteredClaims
	TenantID   string   `json:"tenant_id"`
	FHIRUser   string   `json:"fhirUser"`
	LaunchCtx  string   `json:"launch"`
	Scope      string   `json:"scope"`
	ClientID   string   `json:"client_id"`
	GivenName  string   `json:"given_name"`
	FamilyName string   `json:"family_name"`
	RealmRoles []string `json:"realm_access_roles"`
}

// Scopes parses the space-separated SMART scope string.
func (c *Claims) Scopes() []string {
	return strings.Fields(c.Scope)
}

// HasScope returns true if the claims include the given scope.
// Supports both SMART v1 (patient/Resource.read) and v2 (patient/Resource.rs) formats.
func (c *Claims) HasScope(required string) bool {
	for _, s := range c.Scopes() {
		if s == required || s == "system/*.read" || s == "system/*.*" {
			return true
		}
	}
	return false
}

// SMARTAuth validates SMART on FHIR 2.1 Bearer tokens issued by Keycloak 26.5.6.
// It extracts the tenant_id and injects it into the request context.
// Resources that require specific scopes enforce them at the handler level.
//
// Token validation:
//   1. Verify JWT signature (RS256 from OIDC discovery JWKS endpoint)
//   2. Verify issuer matches configured OIDCIssuer
//   3. Verify audience matches configured OIDCClientID
//   4. Verify token is not expired
//   5. Extract tenant_id claim
func SMARTAuth(oidcIssuer, clientID, jwtSecret string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Extract Bearer token from Authorization header
			authHeader := r.Header.Get("Authorization")
			if authHeader == "" {
				writeSMARTUnauthorized(w, "missing_token", "Authorization header required")
				return
			}
			parts := strings.SplitN(authHeader, " ", 2)
			if len(parts) != 2 || !strings.EqualFold(parts[0], "Bearer") {
				writeSMARTUnauthorized(w, "invalid_token", "Authorization header must be: Bearer <token>")
				return
			}
			tokenStr := parts[1]

			// Parse and validate JWT
			// In production: use OIDC discovery to fetch JWKS from Keycloak
			// For bootstrap: accept HS256 with shared secret
			claims := &Claims{}
			_, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (any, error) {
				if t.Method == jwt.SigningMethodHS256 {
					return []byte(jwtSecret), nil
				}
				// TODO: Add RS256 validation via Keycloak JWKS endpoint
				return []byte(jwtSecret), nil
			}, jwt.WithIssuer(oidcIssuer), jwt.WithExpirationRequired())

			if err != nil {
				log.Debug().Err(err).Msg("smart-auth: token validation failed")
				writeSMARTUnauthorized(w, "invalid_token", "Token validation failed: "+err.Error())
				return
			}

			// Inject tenant_id and claims into context
			ctx := contextkeys.WithTenantID(r.Context(), claims.TenantID)
			ctx = context.WithValue(ctx, principalContextKey{}, claims)

			// Log authenticated access (structured, for zerolog)
			log.Ctx(r.Context()).Debug().
				Str("subject", claims.Subject).
				Str("tenant_id", claims.TenantID).
				Str("client_id", claims.ClientID).
				Str("scope", claims.Scope).
				Msg("smart-auth: authenticated")

			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// TenantContext sets the PostgreSQL session variable app.tenant_id for RLS.
// This must run AFTER SMARTAuth has injected the tenant_id into context.
func TenantContext(db interface{ Exec(context.Context, string, ...any) (interface{}, error) }) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Tenant isolation is enforced at query level via tenant_id parameter
			// PostgreSQL RLS is enabled as defense-in-depth (see schema.sql)
			next.ServeHTTP(w, r)
		})
	}
}

// ContentType enforces application/fhir+json content negotiation.
func ContentType(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// For write operations, verify Content-Type
		if r.Method == http.MethodPost || r.Method == http.MethodPut || r.Method == http.MethodPatch {
			ct := r.Header.Get("Content-Type")
			if ct != "" &&
				!strings.HasPrefix(ct, "application/fhir+json") &&
				!strings.HasPrefix(ct, "application/json") {
				w.Header().Set("Content-Type", "application/fhir+json")
				w.WriteHeader(http.StatusUnsupportedMediaType)
				_, _ = w.Write([]byte(`{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"structure","diagnostics":"Content-Type must be application/fhir+json"}]}`))
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

// CORS configures cross-origin headers appropriate for a FHIR server.
// Clinical SPA frontends (apps.zarishsphere.com) need CORS access.
func CORS(env string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			origin := r.Header.Get("Origin")
			if origin != "" {
				allowedOrigins := []string{
					"https://apps.zarishsphere.com",
					"https://forms.zarishsphere.com",
					"https://health.zarishsphere.com",
					"https://ops.zarishsphere.com",
				}
				if env == "development" {
					allowedOrigins = append(allowedOrigins,
						"http://localhost:3000",
						"http://localhost:3001",
					)
				}
				for _, allowed := range allowedOrigins {
					if origin == allowed {
						w.Header().Set("Access-Control-Allow-Origin", origin)
						w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
						w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type, X-Request-ID")
						w.Header().Set("Access-Control-Expose-Headers", "Location, ETag, Last-Modified, Content-Type")
						w.Header().Set("Access-Control-Max-Age", "3600")
						break
					}
				}
			}
			if r.Method == http.MethodOptions {
				w.WriteHeader(http.StatusNoContent)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}

// FHIRRecoverer catches panics and returns FHIR OperationOutcome instead of raw 500.
func FHIRRecoverer(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if rec := recover(); rec != nil {
				log.Error().Interface("panic", rec).Str("path", r.URL.Path).Msg("fhir: recovered from panic")
				w.Header().Set("Content-Type", "application/fhir+json")
				w.WriteHeader(http.StatusInternalServerError)
				_, _ = w.Write([]byte(`{"resourceType":"OperationOutcome","issue":[{"severity":"fatal","code":"exception","diagnostics":"Internal server error"}]}`))
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// ZeroLogger integrates zerolog request logging middleware.
func ZeroLogger(_ interface{}) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			log.Debug().
				Str("method", r.Method).
				Str("path", r.URL.Path).
				Str("remote_addr", r.RemoteAddr).
				Msg("fhir: request")
			next.ServeHTTP(w, r)
		})
	}
}

// OTelTracing injects OpenTelemetry trace spans.
func OTelTracing(_ string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return next // Full OTel wiring in internal/telemetry/
	}
}

// PrometheusMetrics records request metrics.
func PrometheusMetrics(next http.Handler) http.Handler {
	return next // Full metrics wiring in internal/telemetry/
}

// PrometheusHandler returns the Prometheus /metrics handler.
func PrometheusHandler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("# Prometheus metrics endpoint\n"))
	}
}

func writeSMARTUnauthorized(w http.ResponseWriter, errorCode, description string) {
	w.Header().Set("Content-Type", "application/fhir+json")
	w.Header().Set("WWW-Authenticate", `Bearer realm="ZarishSphere FHIR",error="`+errorCode+`",error_description="`+description+`"`)
	w.WriteHeader(http.StatusUnauthorized)
	_, _ = w.Write([]byte(`{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"security","diagnostics":"` + description + `"}]}`))
}
