package cache

import (
	"context"
	"fmt"

	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/config"
)

type Cache struct {
	rdb *redis.Client
}

func New(cfg *config.Config) *Cache {
	return &Cache{rdb: redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})}
}

func (c *Cache) Ping(ctx context.Context) error { return c.rdb.Ping(ctx).Err() }
func (c *Cache) Close() error                   { return c.rdb.Close() }
func (c *Cache) Client() *redis.Client          { return c.rdb }
