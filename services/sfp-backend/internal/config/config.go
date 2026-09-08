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
	JWTExpire        time.Duration
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

	InternalJobToken string
	IntelJobsURL     string
	QuantJobsURL     string

	InfluxURL      string
	InfluxToken    string
	InfluxOrg      string
	InfluxBucketUS string
	InfluxBucketCN string

	TransportCryptoEnabled      bool
	TransportCryptoMode         string
	TransportCryptoAlgorithm    string
	TransportCryptoKID          string
	TransportCryptoPublicKey    string
	TransportCryptoPrivateKey   string
	TransportCryptoLegacyPairs  string
	TransportCryptoEnabledPaths string
	TransportCryptoRequiredPaths string
}

func Load() (*Config, error) {
	cfg := &Config{
		ListenAddr:       env("LISTEN_ADDR", ":9099"),
		JWTSecret:        strings.TrimSpace(os.Getenv("JWT_SECRET_KEY")),
		JWTAlgorithm:     env("JWT_ALGORITHM", "HS256"),
		AppSameTimeLogin: envBool("APP_SAME_TIME_LOGIN", true),

		MySQLHost:     env("DB_HOST", "ruoyi-mysql"),
		MySQLPort:     envInt("DB_PORT", 3306),
		MySQLUser:     env("DB_USERNAME", "root"),
		MySQLPassword: os.Getenv("DB_PASSWORD"),
		MySQLDatabase: env("DB_DATABASE", "sentiment-ai"),

		RedisHost:     env("REDIS_HOST", "ruoyi-redis"),
		RedisPort:     envInt("REDIS_PORT", 6379),
		RedisPassword: os.Getenv("REDIS_PASSWORD"),
		RedisDB:       envInt("REDIS_DATABASE", 2),

		InternalJobToken: os.Getenv("INTERNAL_JOB_TOKEN"),
		IntelJobsURL:     env("INTEL_JOBS_URL", "http://sentiment-intel:9099"),
		QuantJobsURL:     env("QUANT_JOBS_URL", "http://sentiment-data:9099"),

		InfluxURL:      env("INFLUX_URL", "http://sentiment-influxdb:8086"),
		InfluxToken:    os.Getenv("INFLUX_TOKEN"),
		InfluxOrg:      env("INFLUX_ORG", "sfp"),
		InfluxBucketUS: env("INFLUX_BUCKET_US", "market_us"),
		InfluxBucketCN: env("INFLUX_BUCKET_CN", "market_cn"),

		TransportCryptoEnabled:       envBool("TRANSPORT_CRYPTO_ENABLED", false),
		TransportCryptoMode:          env("TRANSPORT_CRYPTO_MODE", "optional"),
		TransportCryptoAlgorithm:     env("TRANSPORT_CRYPTO_ALGORITHM", "RSA_OAEP_AES_256_GCM"),
		TransportCryptoKID:           env("TRANSPORT_CRYPTO_KID", "default"),
		TransportCryptoPublicKey:     os.Getenv("TRANSPORT_CRYPTO_PUBLIC_KEY"),
		TransportCryptoPrivateKey:    os.Getenv("TRANSPORT_CRYPTO_PRIVATE_KEY"),
		TransportCryptoLegacyPairs:   env("TRANSPORT_CRYPTO_LEGACY_KEY_PAIRS", "[]"),
		TransportCryptoEnabledPaths:  env("TRANSPORT_CRYPTO_ENABLED_PATHS", "/open/sync/token,/open/sync/pull"),
		TransportCryptoRequiredPaths: env("TRANSPORT_CRYPTO_REQUIRED_PATHS", "/open/sync/token,/open/sync/pull"),
	}

	jwtMinutes := envInt("JWT_EXPIRE_MINUTES", 480)
	cfg.JWTExpire = time.Duration(jwtMinutes) * time.Minute
	redisMinutes := envInt("JWT_REDIS_EXPIRE_MINUTES", 480)
	cfg.JWTRedisExpire = time.Duration(redisMinutes) * time.Minute

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
