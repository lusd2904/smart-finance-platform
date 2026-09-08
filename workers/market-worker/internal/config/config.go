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

	InfluxURL      string
	InfluxToken    string
	InfluxOrg      string
	InfluxBucketUS string
	InfluxBucketCN string

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
	ConsumerPollInterval time.Duration
	ReclaimInterval      time.Duration

	LongbridgeAppKey      string
	LongbridgeAppSecret   string
	LongbridgeAccessToken string
	LongbridgeRegion      string
	LongbridgeHTTPURL     string
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

		InfluxURL:      env("INFLUX_URL", "http://sentiment-influxdb:8086"),
		InfluxToken:    env("INFLUX_TOKEN", ""),
		InfluxOrg:      env("INFLUX_ORG", "longbridge"),
		InfluxBucketUS: env("INFLUX_BUCKET_US", "market_us"),
		InfluxBucketCN: env("INFLUX_BUCKET_CN", "market_data"),

		MySQLHost:     env("DB_HOST", "sentiment-mysql"),
		MySQLPort:     envInt("DB_PORT", 3306),
		MySQLUser:     env("DB_USERNAME", "root"),
		MySQLPassword: env("DB_PASSWORD", ""),
		MySQLDatabase: env("DB_DATABASE", "ruoyi-fastapi"),

		SymbolInterval:    envFloat("KLINE_SYMBOL_INTERVAL", 0.4),
		SourceInterval:    envFloat("KLINE_SOURCE_INTERVAL", 0.8),
		SkipMinBars:       envInt("KLINE_SKIP_MIN_BARS", 200),
		SkipFreshDays:     envInt("KLINE_SKIP_FRESH_DAYS", 10),
		VisibilityTimeout: time.Duration(envInt("JOB_VISIBILITY_TIMEOUT_S", 900)) * time.Second,
		MaxRetries:        envInt("JOB_MAX_RETRIES", 3),
		WorkerPort:        envInt("WORKER_PORT", 9098),

		InternalJobsURL:  internalJobsURL(),
		InternalJobToken:  env("INTERNAL_JOB_TOKEN", ""),

		ConsumerPollInterval: 200 * time.Millisecond,
		ReclaimInterval:      30 * time.Second,

		LongbridgeAppKey:      firstEnv("LONGPORT_APP_KEY", "LONGBRIDGE_APP_KEY"),
		LongbridgeAppSecret:   firstEnv("LONGPORT_APP_SECRET", "LONGBRIDGE_APP_SECRET"),
		LongbridgeAccessToken: firstEnv("LONGPORT_ACCESS_TOKEN", "LONGBRIDGE_ACCESS_TOKEN"),
		LongbridgeRegion:      envOr("cn", "LONGPORT_REGION", "LONGBRIDGE_REGION"),
		LongbridgeHTTPURL:     firstEnv("LONGPORT_HTTP_URL", "LONGBRIDGE_HTTP_URL"),
	}
}

func firstEnv(keys ...string) string {
	for _, key := range keys {
		if v := strings.TrimSpace(os.Getenv(key)); v != "" {
			return v
		}
	}
	return ""
}

func envOr(fallback string, keys ...string) string {
	if v := firstEnv(keys...); v != "" {
		return v
	}
	return fallback
}

func internalJobsURL() string {
	if v := strings.TrimSpace(os.Getenv("INTERNAL_JOBS_URL")); v != "" {
		return v
	}
	return "http://sfp-backend:9099/internal/jobs/run"
}

func (c Config) BucketForMarket(market string) string {
	if strings.EqualFold(market, "US") {
		return c.InfluxBucketUS
	}
	return c.InfluxBucketCN
}
