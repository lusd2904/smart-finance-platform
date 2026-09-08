package scheduler

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

const (
	HeartbeatKey = "sfp:scheduler:heartbeat"
)

var queueKeys = []string{
	"sfp:job:queue",
	"sfp:job:queue:market",
	"sfp:job:queue:quant",
	"sfp:job:queue:llm",
}

type Runtime struct {
	redis *redis.Client
}

func New(rdb *redis.Client) *Runtime {
	return &Runtime{redis: rdb}
}

func (r *Runtime) ReadHeartbeat(ctx context.Context) (map[string]interface{}, error) {
	if r.redis == nil {
		return nil, nil
	}
	raw, err := r.redis.Get(ctx, HeartbeatKey).Result()
	if err != nil || raw == "" {
		return nil, nil
	}
	var data map[string]interface{}
	if err := json.Unmarshal([]byte(raw), &data); err != nil {
		return nil, nil
	}
	return data, nil
}

func IsAlive(heartbeat map[string]interface{}) bool {
	if heartbeat == nil {
		return false
	}
	v, ok := heartbeat["alive"]
	if !ok {
		return false
	}
	switch x := v.(type) {
	case bool:
		return x
	case string:
		return x == "true" || x == "1"
	default:
		return false
	}
}

func (r *Runtime) QueueDepth(ctx context.Context) int {
	if r.redis == nil {
		return 0
	}
	total := 0
	for _, key := range queueKeys {
		n, err := r.redis.LLen(ctx, key).Result()
		if err != nil {
			continue
		}
		total += int(n)
	}
	return total
}

func JobsLiteSnapshot(ctx context.Context, rt *Runtime) map[string]interface{} {
	heartbeat, _ := rt.ReadHeartbeat(ctx)
	alive := IsAlive(heartbeat)
	running := []interface{}{}
	if alive {
		if raw, ok := heartbeat["running"].([]interface{}); ok {
			running = raw
		}
	}
	queueDepth := 0
	if alive {
		if v, ok := heartbeat["queueDepth"]; ok {
			switch x := v.(type) {
			case float64:
				queueDepth = int(x)
			case int:
				queueDepth = x
			case int64:
				queueDepth = int(x)
			case string:
				var n int
				fmt.Sscanf(x, "%d", &n)
				queueDepth = n
			}
		}
	} else {
		queueDepth = rt.QueueDepth(ctx)
	}
	heartbeatAt := nilString(heartbeat, "ts")
	return map[string]interface{}{
		"code":    200,
		"msg":     "操作成功",
		"channel": "jobs",
		"data": map[string]interface{}{
			"queueDepth":     queueDepth,
			"running":        running,
			"schedulerAlive": alive,
			"heartbeatAt":    heartbeatAt,
		},
	}
}

func nilString(m map[string]interface{}, key string) interface{} {
	if m == nil {
		return nil
	}
	return m[key]
}
