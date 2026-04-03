# ZarishSphere FHIR R5 Engine — Makefile
# Usage: make <target>
# All targets are idempotent and safe to run repeatedly.

.PHONY: all build test lint security clean dev migrate-up migrate-down \
        docker-build docker-push helm-lint help

# ── Variables ──────────────────────────────────────────────────────────────
GO          := go
GOTEST      := $(GO) test
GOBUILD     := $(GO) build
BINARY      := zs-fhir-engine
CMD         := ./cmd/server
REGISTRY    := ghcr.io/zarishsphere
IMAGE       := $(REGISTRY)/zs-core-fhir-engine
VERSION     ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
BUILD_TIME  := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
LDFLAGS     := -w -s -X 'main.Version=$(VERSION)' -X 'main.BuildTime=$(BUILD_TIME)'

# PostgreSQL 18.3 + TimescaleDB 2.25 for local dev
DB_DSN      ?= postgres://zs_fhir_app:changeme@localhost:5432/zarishsphere?sslmode=disable
MIGRATIONS  := ./migrations

# ── Default target ─────────────────────────────────────────────────────────
all: lint test build

# ── Build ──────────────────────────────────────────────────────────────────
build: ## Build the FHIR engine binary
	CGO_ENABLED=0 $(GOBUILD) -ldflags="$(LDFLAGS)" -o $(BINARY) $(CMD)
	@echo "Built: $(BINARY) v$(VERSION)"

build-arm64: ## Build for ARM64 (Raspberry Pi 5)
	CGO_ENABLED=0 GOOS=linux GOARCH=arm64 $(GOBUILD) -ldflags="$(LDFLAGS)" -o $(BINARY)-arm64 $(CMD)
	@echo "Built ARM64: $(BINARY)-arm64"

# ── Test ───────────────────────────────────────────────────────────────────
test: ## Run all tests with race detector and coverage
	$(GOTEST) ./... -race -coverprofile=coverage.out -covermode=atomic -timeout=120s

test-unit: ## Run unit tests only (fast, no Docker)
	$(GOTEST) ./... -race -tags=unit -timeout=30s

test-integration: ## Run integration tests (requires Docker for testcontainers)
	$(GOTEST) ./... -race -tags=integration -timeout=120s

test-coverage: test ## Show coverage report in browser
	$(GO) tool cover -html=coverage.out

test-coverage-pct: test ## Print coverage percentage
	@$(GO) tool cover -func=coverage.out | tail -1 | awk '{print $$3}'

# ── Lint ───────────────────────────────────────────────────────────────────
lint: ## Run golangci-lint
	golangci-lint run ./... --timeout=5m

lint-fix: ## Run golangci-lint with auto-fix
	golangci-lint run ./... --fix

fmt: ## Format Go code
	gofmt -w .
	$(GO) mod tidy

vet: ## Run go vet
	$(GO) vet ./...

# ── Security ───────────────────────────────────────────────────────────────
security: ## Run security scans (trivy + gitleaks)
	trivy fs --severity CRITICAL,HIGH .
	gitleaks detect --source=. --verbose

# ── Database ───────────────────────────────────────────────────────────────
migrate-up: ## Apply all pending database migrations
	migrate -path $(MIGRATIONS) -database "$(DB_DSN)" up
	@echo "Migrations applied"

migrate-down: ## Roll back last migration
	migrate -path $(MIGRATIONS) -database "$(DB_DSN)" down 1
	@echo "Migration rolled back"

migrate-status: ## Show migration status
	migrate -path $(MIGRATIONS) -database "$(DB_DSN)" version

# ── Docker ─────────────────────────────────────────────────────────────────
docker-build: ## Build Docker image (amd64)
	docker build \
		-f deploy/Dockerfile \
		--build-arg VERSION=$(VERSION) \
		--build-arg BUILD_TIME=$(BUILD_TIME) \
		-t $(IMAGE):$(VERSION) \
		-t $(IMAGE):latest \
		.

docker-build-multiarch: ## Build multi-arch image (amd64 + arm64 for Raspberry Pi 5)
	docker buildx build \
		-f deploy/Dockerfile \
		--platform linux/amd64,linux/arm64 \
		--build-arg VERSION=$(VERSION) \
		--build-arg BUILD_TIME=$(BUILD_TIME) \
		-t $(IMAGE):$(VERSION) \
		-t $(IMAGE):latest \
		--push \
		.

docker-push: ## Push image to GHCR
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):latest

# ── Helm ───────────────────────────────────────────────────────────────────
helm-lint: ## Lint Helm chart
	helm lint deploy/helm/

helm-template: ## Render Helm templates locally
	helm template zs-fhir-engine deploy/helm/ --set image.tag=$(VERSION)

helm-package: ## Package Helm chart
	helm package deploy/helm/ --version $(VERSION)

helm-push: ## Push Helm chart to GHCR OCI registry
	helm push zs-core-fhir-engine-$(VERSION).tgz oci://ghcr.io/zarishsphere/charts

# ── Local Development ──────────────────────────────────────────────────────
dev: ## Start local development server (requires local PostgreSQL + NATS)
	ZS_FHIR_ENV=development \
	ZS_FHIR_AUTH_JWT_SECRET=dev_secret_not_for_production \
	$(GO) run $(CMD)

dev-docker: ## Start full local stack with Docker Compose
	docker compose -f ../../zs-iac-dev-environment/docker-compose.yml up -d
	@echo "Waiting for PostgreSQL..."
	@sleep 5
	$(MAKE) migrate-up
	$(MAKE) dev

# ── Clean ──────────────────────────────────────────────────────────────────
clean: ## Remove build artifacts
	rm -f $(BINARY) $(BINARY)-arm64 coverage.out
	$(GO) clean -cache

# ── Help ───────────────────────────────────────────────────────────────────
help: ## Show this help message
	@echo "ZarishSphere FHIR R5 Engine — Makefile targets:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
