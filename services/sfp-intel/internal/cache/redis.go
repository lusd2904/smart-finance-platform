package cache

import (
	"context"
	"fmt"

	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/config"
)

type Client struct {
	rdb *redis.Client
}

func New(cfg *config.Config) *Client {
	return &Client{rdb: redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})}
}

func (c *Client) Client() *redis.Client { return c.rdb }

func (c *Client) Ping(ctx context.Context) error {
	return c.rdb.Ping(ctx).Err()
}

func (c *Client) Close() error { return c.rdb.Close() }
