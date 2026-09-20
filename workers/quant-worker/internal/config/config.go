package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	RedisHost     string
	RedisPort     int
	RedisPassword string
	RedisDB       int

	MySQLHost     string
	MySQLPort     int
	MySQLUser     string
	MySQLPassword string
	MySQLDatabase string

	SymbolInterval       float64
	SourceInterval       float64
	SkipMinBars          int
	SkipFreshDays        int
	VisibilityTimeout    time.Duration
	MaxRetries           int
	WorkerPort           int
	InternalJobsURL      string
	InternalJobToken     string
	JWTSecret            string
	CredentialKey        string
	AppEnv               string
	ConsumerPollInterval time.Duration
	ReclaimInterval      time.Duration
}

func env(key, fallback string) string {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	return v
}

func envInt(key string, fallback int) int {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	n, err := strconv.Atoi(raw)
	if err != nil || n < 0 {
		return fallback
	}
	return n
}

func envFloat(key string, fallback float64) float64 {
	raw := strings.TrimSpace(os.Getenv(key))
	if raw == "" {
		return fallback
	}
	n, err := strconv.ParseFloat(raw, 64)
	if err != nil || n < 0 {
		return fallback
	}
	return n
}

func Load() Config {
	return Config{
		RedisHost:     env("REDIS_HOST", "ruoyi-redis"),
		RedisPort:     envInt("REDIS_PORT", 6379),
		RedisPassword: env("REDIS_PASSWORD", ""),
		RedisDB:       envInt("REDIS_DATABASE", 2),

		MySQLHost:     env("DB_HOST", "sentiment-mysql"),
		MySQLPort:     envInt("DB_PORT", 3306),
		MySQLUser:     env("DB_USERNAME", "root"),
		MySQLPassword: env("DB_PASSWORD", ""),
		MySQLDatabase: env("DB_DATABASE", "sentiment-ai"),

		SymbolInterval:    envFloat("KLINE_SYMBOL_INTERVAL", 0.4),
		SourceInterval:    envFloat("KLINE_SOURCE_INTERVAL", 0.8),
		SkipMinBars:       envInt("KLINE_SKIP_MIN_BARS", 200),
		SkipFreshDays:     envInt("KLINE_SKIP_FRESH_DAYS", 10),
		VisibilityTimeout: time.Duration(envInt("JOB_VISIBILITY_TIMEOUT_S", 900)) * time.Second,
		MaxRetries:        envInt("JOB_MAX_RETRIES", 3),
		WorkerPort:        envInt("WORKER_PORT", 9098),

		InternalJobsURL:  internalJobsURL(),
		InternalJobToken: env("INTERNAL_JOB_TOKEN", ""),
		JWTSecret:        env("JWT_SECRET_KEY", env("JWT_SECRET", "")),
		CredentialKey:    env("CREDENTIAL_ENCRYPTION_KEY", ""),
		AppEnv:           env("APP_ENV", "dev"),

		ConsumerPollInterval: 200 * time.Millisecond,
		ReclaimInterval:      30 * time.Second,
	}
}

func internalJobsURL() string {
	if v := strings.TrimSpace(os.Getenv("INTERNAL_JOBS_URL")); v != "" {
		return v
	}
	return "http://sfp-backend:9099/internal/jobs/run"
}
