package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

const QueueKeyLLM = "sfp:job:queue:llm"
const group = "llm"

var llmJobTypes = map[string]bool{
	"sentiment_collect": true, "sentiment_analyze": true, "watchlist_analyze": true,
	"daily_review": true, "req_send": true, "req_summarize": true, "feishu_push": true,
	"stock_pick_run": true, "market_review": true, "ai_analyze": true, "ai_batch": true, "user_notice": true,
}

type Job struct {
	Type       string                 `json:"type"`
	Payload    map[string]interface{} `json:"payload"`
	JobID      string                 `json:"jobId"`
	Queue      string                 `json:"queue"`
	EnqueuedAt string                 `json:"enqueuedAt"`
	Retries    int                    `json:"retries"`
}

type Handler func(ctx context.Context, job Job) (interface{}, error)

type Consumer struct {
	redis *redis.Client
	handler Handler
	visibilityTimeout time.Duration
	maxRetries int
	pollInterval time.Duration
	reclaimInterval time.Duration
	logger *slog.Logger
}

func NewConsumer(rdb *redis.Client, handler Handler, visibility time.Duration, maxRetries int, poll, reclaim time.Duration, logger *slog.Logger) *Consumer {
	return &Consumer{redis: rdb, handler: handler, visibilityTimeout: visibility, maxRetries: maxRetries, pollInterval: poll, reclaimInterval: reclaim, logger: logger}
}

func decode(raw string) (*Job, error) {
	var job Job
	if err := json.Unmarshal([]byte(raw), &job); err != nil {
		return nil, err
	}
	if !llmJobTypes[job.Type] {
		return nil, fmt.Errorf("unknown job type: %s", job.Type)
	}
	if job.Payload == nil {
		job.Payload = map[string]interface{}{}
	}
	return &job, nil
}

func (c *Consumer) Run(ctx context.Context) error {
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		raw, err := c.redis.RPopLPush(ctx, QueueKeyLLM, fmt.Sprintf("sfp:job:processing:%s", group)).Result()
		if err == redis.Nil {
			time.Sleep(c.pollInterval)
			continue
		}
		if err != nil {
			time.Sleep(time.Second)
			continue
		}
		job, err := decode(raw)
		if err != nil {
			_ = c.redis.LRem(ctx, fmt.Sprintf("sfp:job:processing:%s", group), 1, raw).Err()
			continue
		}
		_, runErr := c.handler(ctx, *job)
		_ = c.redis.LRem(ctx, fmt.Sprintf("sfp:job:processing:%s", group), 1, raw).Err()
		if runErr != nil && job.Retries < c.maxRetries {
			job.Retries++
			retryRaw, _ := json.Marshal(job)
			_ = c.redis.LPush(ctx, QueueKeyLLM, retryRaw).Err()
		} else if runErr != nil {
			deadRaw, _ := json.Marshal(map[string]interface{}{"job": job, "error": runErr.Error()})
			_ = c.redis.LPush(ctx, fmt.Sprintf("sfp:job:dead:%s", group), deadRaw).Err()
		}
	}
}

func (c *Consumer) QueueDepth(ctx context.Context) int64 {
	n, _ := c.redis.LLen(ctx, QueueKeyLLM).Result()
	return n
}

func Encode(jobType string, payload map[string]interface{}) (string, error) {
	job := Job{Type: jobType, Payload: payload, JobID: strings.ReplaceAll(uuid.NewString(), "-", ""), Queue: group, EnqueuedAt: time.Now().Format("2006-01-02 15:04:05")}
	raw, err := json.Marshal(job)
	return string(raw), err
}
