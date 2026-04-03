// ZarishSphere FHIR R5 Engine — entry point
// FHIR R5 (5.0.0) | Go 1.26.1 | PostgreSQL 18.3 | Keycloak 26.5.6
// Governance: RFC-0001, ADR-0001, ADR-0002, ADR-0003
package main

import (
	"context"
	"errors"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

func main() {
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	log.Logger = log.With().Caller().Logger()

	log.Info().
		Str("service", "zs-core-fhir-engine").
		Str("fhir", "R5/5.0.0").
		Msg("starting")

	// Placeholder — full wiring happens in internal packages
	srv := &http.Server{
		Addr:         ":8080",
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 60 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	done := make(chan struct{})
	go func() {
		quit := make(chan os.Signal, 1)
		signal.Notify(quit, syscall.SIGTERM, syscall.SIGINT)
		<-quit
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			log.Error().Err(err).Msg("shutdown error")
		}
		close(done)
	}()

	if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal().Err(err).Msg("server error")
	}
	<-done
	log.Info().Msg("stopped")
}
