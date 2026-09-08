package cache

import (
	"context"
	"encoding/json"
	"time"

	"github.com/redis/go-redis/v9"
)

const BoardQuotesKey = "sfp:cache:board:quotes"
const BoardQuotesTTL = 15 * time.Minute

func SetJSON(ctx context.Context, rdb *redis.Client, key string, value interface{}, ttl time.Duration) error {
	raw, err := json.Marshal(value)
	if err != nil {
		return err
	}
	return rdb.Set(ctx, key, raw, ttl).Err()
}

func GetJSON(ctx context.Context, rdb *redis.Client, key string, dest interface{}) (bool, error) {
	raw, err := rdb.Get(ctx, key).Bytes()
	if err == redis.Nil {
		return false, nil
	}
	if err != nil {
		return false, err
	}
	if err := json.Unmarshal(raw, dest); err != nil {
		return false, err
	}
	return true, nil
}

func PutScheduledBoard(ctx context.Context, rdb *redis.Client, payload interface{}) error {
	return SetJSON(ctx, rdb, "readmodel:scheduled:board", payload, BoardQuotesTTL)
}
