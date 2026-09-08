package jobs

import (
	"context"
	"encoding/json"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
	"github.com/redis/go-redis/v9"
)

type EncKeys struct {
	CredentialKey string
	JWTSecret     string
	AppEnv        string
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}

func jsonBytes(v interface{}) ([]byte, error) {
	return json.Marshal(v)
}

func readHalt(ctx context.Context, rdb *redis.Client) tradeexec.HaltState {
	if rdb == nil {
		return tradeexec.HaltState{}
	}
	raw, err := rdb.Get(ctx, tradeexec.HaltRedisKey).Result()
	if err != nil || raw == "" {
		return tradeexec.HaltState{}
	}
	return tradeexec.ParseHalt(raw)
}

func payloadInt(payload map[string]interface{}, key string) int {
	if payload == nil {
		return 0
	}
	switch v := payload[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	case int64:
		return int(v)
	case json.Number:
		n, _ := v.Int64()
		return int(n)
	case string:
		var n int
		_, _ = parseInt(v, &n)
		return n
	default:
		return 0
	}
}

func payloadString(payload map[string]interface{}, key string) string {
	if payload == nil || payload[key] == nil {
		return ""
	}
	if s, ok := payload[key].(string); ok {
		return s
	}
	return ""
}

func parseInt(s string, n *int) (int, error) {
	var v int
	for _, r := range s {
		if r < '0' || r > '9' {
			break
		}
		v = v*10 + int(r-'0')
	}
	*n = v
	return v, nil
}

func uniqueInts(sets ...[]int) []int {
	seen := map[int]struct{}{}
	var out []int
	for _, set := range sets {
		for _, id := range set {
			if id <= 0 {
				continue
			}
			if _, ok := seen[id]; ok {
				continue
			}
			seen[id] = struct{}{}
			out = append(out, id)
		}
	}
	return out
}
