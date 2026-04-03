module github.com/zarishsphere/zs-core-fhir-engine

go 1.26.1

require (
	github.com/damedic/fhir-toolbox-go v0.0.0-20250101000000-000000000000
	github.com/fastenhealth/gofhir-models v0.0.7
	github.com/go-chi/chi/v5 v5.2.1
	github.com/go-chi/render v1.0.3
	github.com/google/uuid v1.6.0
	github.com/jackc/pgx/v5 v5.7.2
	github.com/nats-io/nats.go v1.39.0
	github.com/rs/zerolog v1.33.0
	github.com/spf13/viper v1.20.1
	github.com/stretchr/testify v1.10.0
	github.com/testcontainers/testcontainers-go v0.36.0
	github.com/zarishsphere/zs-pkg-go-fhir v0.1.0
	go.opentelemetry.io/otel v1.35.0
	go.opentelemetry.io/otel/exporters/prometheus v0.57.0
	go.opentelemetry.io/otel/metric v1.35.0
	go.opentelemetry.io/otel/sdk v1.35.0
	go.opentelemetry.io/otel/trace v1.35.0
	go.opentelemetry.io/contrib/instrumentation/net/http/otelhttp v0.60.0
	golang.org/x/crypto v0.37.0
)

require (
	github.com/Masterminds/squirrel v1.5.4
	github.com/golang-jwt/jwt/v5 v5.2.2
	github.com/golang-migrate/migrate/v4 v4.18.3
	github.com/prometheus/client_golang v1.22.0
	github.com/redis/go-redis/v9 v9.7.3
)

replace github.com/zarishsphere/zs-pkg-go-fhir => ../zs-pkg-go-fhir
