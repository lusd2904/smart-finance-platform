package config

import (
	"os"
	"strconv"
	"strings"
	"time"
)

const DefaultTimezone = "Asia/Shanghai"

type Config struct {
	ListenPort int
	Timezone   string

	RedisHost     string
	RedisPort     int
	RedisPassword string
	RedisDB       int

	MySQLHost     string
	MySQLPort     int
	MySQLUser     string
	MySQLPassword string
	MySQLDatabase string

	SyncInterval      time.Duration
	HeartbeatInterval time.Duration
	LockTTL           time.Duration
	LockRenewInterval time.Duration
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

func envDurationSeconds(key string, fallback time.Duration) time.Duration {
	n := envInt(key, int(fallback/time.Second))
	if n <= 0 {
		return fallback
	}
	return time.Duration(n) * time.Second
}

func Load() Config {
	return Config{
		ListenPort: envInt("SCHEDULER_PORT", envInt("WORKER_PORT", 9098)),
		Timezone:   env("SCHEDULER_TZ", env("TZ", DefaultTimezone)),

		RedisHost:     env("REDIS_HOST", "ruoyi-redis"),
		RedisPort:     envInt("REDIS_PORT", 6379),
		RedisPassword: env("REDIS_PASSWORD", ""),
		RedisDB:       envInt("REDIS_DATABASE", 2),

		MySQLHost:     env("DB_HOST", "sentiment-mysql"),
		MySQLPort:     envInt("DB_PORT", 3306),
		MySQLUser:     env("DB_USERNAME", "root"),
		MySQLPassword: env("DB_PASSWORD", ""),
		MySQLDatabase: env("DB_DATABASE", "sentiment-ai"),

		SyncInterval:      envDurationSeconds("SCHEDULER_SYNC_SECONDS", 30*time.Second),
		HeartbeatInterval: envDurationSeconds("SCHEDULER_HEARTBEAT_SECONDS", 8*time.Second),
		LockTTL:           envDurationSeconds("SCHEDULER_LOCK_TTL_SECONDS", 60*time.Second),
		LockRenewInterval: envDurationSeconds("SCHEDULER_LOCK_RENEW_SECONDS", 20*time.Second),
	}
}
