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

	CredentialEncryptionKey string
	XMonitorIngestToken     string
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

		CredentialEncryptionKey: strings.TrimSpace(os.Getenv("CREDENTIAL_ENCRYPTION_KEY")),
		XMonitorIngestToken:     strings.TrimSpace(os.Getenv("SFP_X_MONITOR_INGEST_TOKEN")),
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
