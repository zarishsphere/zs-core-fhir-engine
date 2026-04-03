# ZarishSphere FHIR R5 Engine — Multi-stage Docker build
# Produces a minimal final image that runs on Raspberry Pi 5 (ARM64)
# ADR-0001: Go 1.21.13 single binary, offline-capable

# ── Stage 1: Build ────────────────────────────────────────────────────────
FROM golang:1.21-alpine AS builder

# Install CA certs and git for go get
RUN apk add --no-cache ca-certificates git tzdata

WORKDIR /build

# Cache dependency downloads before copying source
COPY go.mod go.sum ./
RUN go mod download && go mod verify

# Copy source and build
COPY . .

# Build with CGO disabled for a fully static binary
# ldflags: strip debug symbols, inject version
ARG VERSION=1.0.0
ARG BUILD_TIME
RUN CGO_ENABLED=0 GOOS=linux go build \
    -ldflags="-w -s \
      -X 'main.Version=${VERSION}' \
      -X 'main.BuildTime=${BUILD_TIME}'" \
    -o /build/zs-fhir-engine \
    ./cmd/server

# ── Stage 2: Runtime ──────────────────────────────────────────────────────
FROM alpine:3.19

# Install CA certs for HTTPS requests
RUN apk --no-cache add ca-certificates tzdata

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy binary and certificates from builder
COPY --from=builder /build/zs-fhir-engine .
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/

# Change ownership and switch to non-root user
RUN chown -R appuser:appgroup /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/health || exit 1

# Expose port
EXPOSE 8080

# Run the binary
ENTRYPOINT ["/app/zs-fhir-engine"]

# ── Stage 2: Final minimal image ──────────────────────────────────────────
# Use distroless for minimal attack surface
FROM gcr.io/distroless/static-debian12:nonroot

# Non-root user (distroless nonroot = UID 65532)
USER nonroot:nonroot

# Copy only what's needed
COPY --from=builder --chown=nonroot:nonroot /build/zs-fhir-engine /app/zs-fhir-engine
COPY --from=builder /usr/share/zoneinfo /usr/share/zoneinfo
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --chown=nonroot:nonroot migrations/ /app/migrations/
COPY --chown=nonroot:nonroot config/config.yaml /app/config/config.yaml

WORKDIR /app

# FHIR R5 REST API
EXPOSE 8080
# Prometheus metrics
EXPOSE 9090

# Health check — uses /healthz endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD ["/app/zs-fhir-engine", "healthcheck"]

ENTRYPOINT ["/app/zs-fhir-engine"]

# ── Build metadata labels (OCI standard) ──────────────────────────────────
LABEL org.opencontainers.image.title="zs-core-fhir-engine"
LABEL org.opencontainers.image.description="ZarishSphere FHIR R5 Engine"
LABEL org.opencontainers.image.url="https://github.com/zarishsphere/zs-core-fhir-engine"
LABEL org.opencontainers.image.source="https://github.com/zarishsphere/zs-core-fhir-engine"
LABEL org.opencontainers.image.vendor="ZarishSphere"
LABEL org.opencontainers.image.licenses="Apache-2.0"
LABEL org.opencontainers.image.version="${VERSION}"
