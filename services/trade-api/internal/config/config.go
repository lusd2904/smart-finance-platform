package config

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ListenAddr string

	JWTSecret        string
	JWTAlgorithm     string
	JWTRedisExpire   time.Duration
	AppSameTimeLogin bool

	MySQLHost     string
	MySQLPort     int
	MySQLUser     string
	MySQLPassword string
	MySQLDatabase string

	RedisHost     string
	RedisPort     int
	RedisPassword string
	RedisDB       int

	CredentialKey string
	AppEnv        string

	InfluxURL      string
	InfluxToken    string
	InfluxOrg      string
	InfluxBucketUS string
	InfluxBucketCN string
	InfluxTimeout  time.Duration

	InternalJobsURL  string
	InternalJobToken string
}

func Load() (*Config, error) {
	cfg := &Config{
		ListenAddr:       env("LISTEN_ADDR", ":8080"),
		JWTSecret:        strings.TrimSpace(os.Getenv("JWT_SECRET_KEY")),
		JWTAlgorithm:     env("JWT_ALGORITHM", "HS256"),
		AppSameTimeLogin: envBool("APP_SAME_TIME_LOGIN", true),

		MySQLHost:     env("DB_HOST", "sentiment-mysql"),
		MySQLPort:     envInt("DB_PORT", 3306),
		MySQLUser:     env("DB_USERNAME", "root"),
		MySQLPassword: os.Getenv("DB_PASSWORD"),
		MySQLDatabase: env("DB_DATABASE", "sentiment-ai"),

		RedisHost:     env("REDIS_HOST", "ruoyi-redis"),
		RedisPort:     envInt("REDIS_PORT", 6379),
		RedisPassword: os.Getenv("REDIS_PASSWORD"),
		RedisDB:       envInt("REDIS_DATABASE", 2),

		CredentialKey: strings.TrimSpace(os.Getenv("CREDENTIAL_ENCRYPTION_KEY")),
		AppEnv:        env("APP_ENV", "prod"),

		InfluxURL:      env("INFLUX_URL", "http://sentiment-influxdb:8086"),
		InfluxToken:    os.Getenv("INFLUX_TOKEN"),
		InfluxOrg:      env("INFLUX_ORG", "longbridge"),
		InfluxBucketUS: env("INFLUX_BUCKET_US", "market_us"),
		InfluxBucketCN: env("INFLUX_BUCKET_CN", "market_data"),
		InfluxTimeout:  time.Duration(envInt("INFLUX_TIMEOUT_MS", 8000)) * time.Millisecond,

		InternalJobsURL:  internalJobsURL(),
		InternalJobToken: strings.TrimSpace(os.Getenv("INTERNAL_JOB_TOKEN")),
	}

	jwtMinutes := envInt("JWT_REDIS_EXPIRE_MINUTES", 480)
	cfg.JWTRedisExpire = time.Duration(jwtMinutes) * time.Minute

	if cfg.JWTSecret == "" {
		return nil, fmt.Errorf("JWT_SECRET_KEY is required")
	}
	if cfg.MySQLPassword == "" {
		return nil, fmt.Errorf("DB_PASSWORD is required")
	}
	return cfg, nil
}

func (c *Config) MySQLDSN() string {
	return fmt.Sprintf("%s:%s@tcp(%s:%d)/%s?parseTime=true&loc=Local&charset=utf8mb4",
		c.MySQLUser, c.MySQLPassword, c.MySQLHost, c.MySQLPort, c.MySQLDatabase)
}

func env(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func envInt(key string, fallback int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func internalJobsURL() string {
	if v := strings.TrimSpace(os.Getenv("INTERNAL_JOBS_URL")); v != "" {
		return strings.TrimRight(v, "/")
	}
	return "http://sfp-backend:9099/internal/jobs/run"
}

func envBool(key string, fallback bool) bool {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	switch strings.ToLower(v) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}
