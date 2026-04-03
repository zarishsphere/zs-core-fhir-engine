// Package telemetry configures OpenTelemetry 1.35+ tracing, Prometheus metrics,
// and zerolog structured logging for the ZarishSphere FHIR engine.
//
// Observability stack (ADR from ARCHITECTURE.md):
//   Metrics  → Prometheus → Grafana 12.x dashboards
//   Traces   → OpenTelemetry → Tempo 2.7+ → Grafana trace view
//   Logs     → zerolog JSON → Loki 3.4+ → Grafana explore
package telemetry

import (
	"context"
	"fmt"
	"time"

	"github.com/rs/zerolog/log"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/exporters/prometheus"
	"go.opentelemetry.io/otel/metric"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

const (
	serviceName    = "zs-core-fhir-engine"
	serviceVersion = "1.0.0"
)

var (
	// Tracer is the global OpenTelemetry tracer for the FHIR engine.
	Tracer trace.Tracer

	// Meter is the global OpenTelemetry meter for Prometheus metrics.
	Meter metric.Meter

	// FHIR request metrics
	FHIRRequestsTotal  metric.Int64Counter
	FHIRRequestLatency metric.Float64Histogram
	FHIRResourcesTotal metric.Int64UpDownCounter
	FHIRAuditEvents    metric.Int64Counter
)

// ShutdownFunc is called to flush and close telemetry providers.
type ShutdownFunc func()

// Init initialises OpenTelemetry tracing and Prometheus metrics.
// It returns a shutdown function that must be deferred by the caller.
func Init(svcName, otlpEndpoint string) (ShutdownFunc, error) {
	if svcName == "" {
		svcName = serviceName
	}

	res, err := resource.New(context.Background(),
		resource.WithAttributes(
			semconv.ServiceNameKey.String(svcName),
			semconv.ServiceVersionKey.String(serviceVersion),
			semconv.ServiceNamespaceKey.String("zarishsphere"),
		),
		resource.WithFromEnv(),
		resource.WithProcess(),
	)
	if err != nil {
		return nil, fmt.Errorf("telemetry: create resource: %w", err)
	}

	// ── Prometheus metrics exporter ────────────────────────────────────────
	promExporter, err := prometheus.New()
	if err != nil {
		return nil, fmt.Errorf("telemetry: create prometheus exporter: %w", err)
	}

	meterProvider := sdkmetric.NewMeterProvider(
		sdkmetric.WithResource(res),
		sdkmetric.WithReader(promExporter),
	)
	otel.SetMeterProvider(meterProvider)
	Meter = meterProvider.Meter(svcName)

	// ── OTLP trace exporter (Tempo 2.7+) ──────────────────────────────────
	// In production, configure OTLP exporter to send to Tempo.
	// For development/testing, use no-op trace provider.
	tracerProvider := sdktrace.NewTracerProvider(
		sdktrace.WithResource(res),
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
	)
	otel.SetTracerProvider(tracerProvider)
	Tracer = tracerProvider.Tracer(svcName)

	// ── Register FHIR-specific metrics ────────────────────────────────────
	if err := registerFHIRMetrics(); err != nil {
		return nil, fmt.Errorf("telemetry: register fhir metrics: %w", err)
	}

	log.Info().
		Str("service", svcName).
		Str("otlp_endpoint", otlpEndpoint).
		Msg("telemetry: OpenTelemetry initialised")

	return func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := meterProvider.Shutdown(ctx); err != nil {
			log.Error().Err(err).Msg("telemetry: meter provider shutdown error")
		}
		if err := tracerProvider.Shutdown(ctx); err != nil {
			log.Error().Err(err).Msg("telemetry: tracer provider shutdown error")
		}
		log.Info().Msg("telemetry: shutdown complete")
	}, nil
}

func registerFHIRMetrics() error {
	var err error

	// Total FHIR requests by resource type, method, status
	FHIRRequestsTotal, err = Meter.Int64Counter(
		"zs_fhir_requests_total",
		metric.WithDescription("Total FHIR R5 requests by resource type and method"),
		metric.WithUnit("{requests}"),
	)
	if err != nil {
		return err
	}

	// Request latency histogram (buckets in milliseconds)
	FHIRRequestLatency, err = Meter.Float64Histogram(
		"zs_fhir_request_duration_ms",
		metric.WithDescription("FHIR R5 request duration in milliseconds"),
		metric.WithUnit("ms"),
		metric.WithExplicitBucketBoundaries(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
	)
	if err != nil {
		return err
	}

	// Running count of FHIR resources per type per tenant
	FHIRResourcesTotal, err = Meter.Int64UpDownCounter(
		"zs_fhir_resources_total",
		metric.WithDescription("Current count of FHIR resources by type"),
		metric.WithUnit("{resources}"),
	)
	if err != nil {
		return err
	}

	// AuditEvent generation counter
	FHIRAuditEvents, err = Meter.Int64Counter(
		"zs_fhir_audit_events_total",
		metric.WithDescription("Total FHIR AuditEvents generated"),
		metric.WithUnit("{events}"),
	)
	if err != nil {
		return err
	}

	return nil
}

// StartSpan starts a new OpenTelemetry span with FHIR context attributes.
// Always use as: ctx, span := telemetry.StartSpan(ctx, "fhir.Patient.read"); defer span.End()
func StartSpan(ctx context.Context, operationName string) (context.Context, trace.Span) {
	return Tracer.Start(ctx, operationName)
}

// RecordRequest records a completed FHIR request in Prometheus metrics.
func RecordRequest(ctx context.Context, resourceType, method string, statusCode int, durationMs float64) {
	attrs := metric.WithAttributes(
		semconv.HTTPRequestMethodKey.String(method),
	)
	if FHIRRequestsTotal != nil {
		FHIRRequestsTotal.Add(ctx, 1, attrs)
	}
	if FHIRRequestLatency != nil {
		FHIRRequestLatency.Record(ctx, durationMs, attrs)
	}
}
