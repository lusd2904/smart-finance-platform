package scheduler

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/redis/go-redis/v9"
)

const CommandChannel = "sfp:scheduler:command"

type Commander struct {
	redis *redis.Client
}

func NewCommander(rdb *redis.Client) *Commander {
	return &Commander{redis: rdb}
}

func (c *Commander) PublishRun(ctx context.Context, jobID int64) error {
	if c.redis == nil {
		return fmt.Errorf("redis unavailable")
	}
	payload, err := json.Marshal(map[string]interface{}{
		"action": "run",
		"jobId":  jobID,
	})
	if err != nil {
		return err
	}
	return c.redis.Publish(ctx, CommandChannel, payload).Err()
}
