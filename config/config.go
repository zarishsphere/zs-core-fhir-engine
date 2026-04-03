// Package config loads zs-core-fhir-engine configuration via Viper.
// Priority: env vars > config.yaml > defaults
// All secrets come from env vars (ZS_FHIR_*) or Vault injection — never committed files.
package config

import (
	"fmt"
	"strings"
	"time"

	"github.com/rs/zerolog/log"
	"github.com/spf13/viper"
	"github.com/zarishsphere/zs-core-fhir-engine/internal/storage"
)

type Config struct {
	Env            string           `mapstructure:"env"`
	Version        string           `mapstructure:"version"`
	ServiceName    string           `mapstructure:"service_name"`
	MigrationsPath string           `mapstructure:"migrations_path"`
	Server         ServerConfig     `mapstructure:"server"`
	Database       storage.DBConfig `mapstructure:"database"`
	Auth           AuthConfig       `mapstructure:"auth"`
	FHIR           FHIRConfig       `mapstructure:"fhir"`
	OTLP           OTLPConfig       `mapstructure:"otlp"`
	NATS           NATSConfig       `mapstructure:"nats"`
}

type ServerConfig struct {
	Host         string        `mapstructure:"host"`
	Port         int           `mapstructure:"port"`
	ReadTimeout  time.Duration `mapstructure:"read_timeout"`
	WriteTimeout time.Duration `mapstructure:"write_timeout"`
}

func (s ServerConfig) Addr() string { return fmt.Sprintf("%s:%d", s.Host, s.Port) }

type AuthConfig struct {
	OIDCIssuer   string `mapstructure:"oidc_issuer"`
	ClientID     string `mapstructure:"client_id"`
	JWTSecret    string `mapstructure:"jwt_secret"`
	JWKSEndpoint string `mapstructure:"jwks_endpoint"`
}

type FHIRConfig struct {
	BasePath            string `mapstructure:"base_path"`
	MaxRequestBodyBytes int64  `mapstructure:"max_request_body_bytes"`
	DefaultPageSize     int    `mapstructure:"default_page_size"`
	MaxPageSize         int    `mapstructure:"max_page_size"`
	Version             string `mapstructure:"version"`
	ValidateOnCreate    bool   `mapstructure:"validate_on_create"`
	AuditAllReads       bool   `mapstructure:"audit_all_reads"`
}

type OTLPConfig struct {
	Endpoint string `mapstructure:"endpoint"`
	Insecure bool   `mapstructure:"insecure"`
}

type NATSConfig struct {
	URL           string        `mapstructure:"url"`
	ClusterID     string        `mapstructure:"cluster_id"`
	ClientID      string        `mapstructure:"client_id"`
	MaxReconnects int           `mapstructure:"max_reconnects"`
	ReconnectWait time.Duration `mapstructure:"reconnect_wait"`
}

func Load() (*Config, error) {
	v := viper.New()

	v.SetDefault("env", "development")
	v.SetDefault("version", "1.0.0")
	v.SetDefault("service_name", "zs-core-fhir-engine")
	v.SetDefault("migrations_path", "./migrations")
	v.SetDefault("server.host", "0.0.0.0")
	v.SetDefault("server.port", 8080)
	v.SetDefault("server.read_timeout", "30s")
	v.SetDefault("server.write_timeout", "60s")
	v.SetDefault("database.host", "localhost")
	v.SetDefault("database.port", 5432)
	v.SetDefault("database.database", "zarishsphere")
	v.SetDefault("database.user", "zs_fhir_app")
	v.SetDefault("database.sslmode", "disable")
	v.SetDefault("database.max_conns", 25)
	v.SetDefault("database.min_conns", 5)
	v.SetDefault("database.max_conn_life", "30m")
	v.SetDefault("database.max_conn_idle", "5m")
	v.SetDefault("auth.oidc_issuer", "http://localhost:8443/realms/zarishsphere")
	v.SetDefault("auth.client_id", "zs-fhir-engine")
	v.SetDefault("fhir.base_path", "/fhir/R5")
	v.SetDefault("fhir.max_request_body_bytes", 10485760)
	v.SetDefault("fhir.default_page_size", 20)
	v.SetDefault("fhir.max_page_size", 100)
	v.SetDefault("fhir.version", "5.0.0")
	v.SetDefault("fhir.audit_all_reads", true)
	v.SetDefault("otlp.endpoint", "http://localhost:4318")
	v.SetDefault("nats.url", "nats://localhost:4222")
	v.SetDefault("nats.cluster_id", "zarishsphere")
	v.SetDefault("nats.client_id", "zs-fhir-engine")
	v.SetDefault("nats.max_reconnects", 10)

	v.SetConfigName("config")
	v.SetConfigType("yaml")
	v.AddConfigPath("./config")
	v.AddConfigPath(".")
	if err := v.ReadInConfig(); err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			log.Warn().Err(err).Msg("config: file error (using defaults)")
		}
	}

	v.SetEnvPrefix("ZS_FHIR")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	var cfg Config
	if err := v.Unmarshal(&cfg); err != nil {
		return nil, fmt.Errorf("config: unmarshal: %w", err)
	}

	log.Debug().Str("env", cfg.Env).Str("db_host", cfg.Database.Host).Msg("config: loaded")
	return &cfg, nil
}
