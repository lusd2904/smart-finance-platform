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

const (
	QueueKeyLLM = "sfp:job:queue:llm"
	ClaimsKey   = "sfp:job:claims:llm"
	group       = "llm"
)

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
	redis             *redis.Client
	handler           Handler
	visibilityTimeout time.Duration
	maxRetries        int
	pollInterval      time.Duration
	reclaimInterval   time.Duration
	logger            *slog.Logger
}

func NewConsumer(rdb *redis.Client, handler Handler, visibility time.Duration, maxRetries int, poll, reclaim time.Duration, logger *slog.Logger) *Consumer {
	if logger == nil {
		logger = slog.Default()
	}
	return &Consumer{redis: rdb, handler: handler, visibilityTimeout: visibility, maxRetries: maxRetries, pollInterval: poll, reclaimInterval: reclaim, logger: logger}
}

func processingKey() string { return fmt.Sprintf("sfp:job:processing:%s", group) }
func deadKey() string       { return fmt.Sprintf("sfp:job:dead:%s", group) }

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
	c.logger.Info("notify worker consumer started", "queue", QueueKeyLLM)
	nextReclaim := time.Now()
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if time.Now().After(nextReclaim) {
			if err := c.recoverStale(ctx); err != nil {
				c.logger.Warn("stale reclaim failed", "error", err)
			}
			nextReclaim = time.Now().Add(c.reclaimInterval)
		}
		raw, err := c.redis.RPopLPush(ctx, QueueKeyLLM, processingKey()).Result()
		if err == redis.Nil {
			time.Sleep(c.pollInterval)
			continue
		}
		if err != nil {
			c.logger.Warn("rpoplpush failed", "error", err)
			time.Sleep(time.Second)
			continue
		}
		c.runOne(ctx, raw)
	}
}

func (c *Consumer) runOne(ctx context.Context, raw string) {
	job, err := decode(raw)
	if err != nil {
		c.logger.Warn("dropping unparseable job", "error", err)
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		return
	}
	c.claim(ctx, job)
	c.logger.Info("job started", "jobId", job.JobID, "type", job.Type)
	_, runErr := c.handler(ctx, *job)
	_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
	c.unclaim(ctx, job)
	if runErr == nil {
		c.logger.Info("job succeeded", "jobId", job.JobID, "type", job.Type)
		return
	}
	c.logger.Error("job failed", "jobId", job.JobID, "type", job.Type, "error", runErr)
	if job.Retries < c.maxRetries {
		job.Retries++
		retryRaw, _ := json.Marshal(job)
		_ = c.redis.LPush(ctx, QueueKeyLLM, retryRaw).Err()
		c.logger.Warn("job will retry", "jobId", job.JobID, "type", job.Type, "retries", job.Retries, "error", runErr)
		return
	}
	deadRaw, _ := json.Marshal(map[string]interface{}{"job": job, "error": runErr.Error()})
	_ = c.redis.LPush(ctx, deadKey(), deadRaw).Err()
	c.logger.Error("job dead-lettered", "jobId", job.JobID, "type", job.Type, "error", runErr)
}

func (c *Consumer) claim(ctx context.Context, job *Job) {
	if job.JobID == "" {
		return
	}
	_ = c.redis.HSet(ctx, ClaimsKey, job.JobID, time.Now().Unix()).Err()
}

func (c *Consumer) unclaim(ctx context.Context, job *Job) {
	if job.JobID == "" {
		return
	}
	_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
}

func (c *Consumer) recoverStale(ctx context.Context) error {
	claims, err := c.redis.HGetAll(ctx, ClaimsKey).Result()
	if err != nil {
		return err
	}
	entries, err := c.redis.LRange(ctx, processingKey(), 0, -1).Result()
	if err != nil {
		return err
	}
	now := time.Now().Unix()
	reclaimed := 0
	for _, raw := range entries {
		job, decErr := decode(raw)
		if decErr != nil || job == nil {
			_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
			continue
		}
		if !isStaleClaim(claims[job.JobID], now, c.visibilityTimeout) {
			continue
		}
		c.requeueOrDead(ctx, raw, job, "visibility timeout reclaim")
		reclaimed++
	}
	if reclaimed > 0 {
		c.logger.Info("reclaimed stale processing jobs", "count", reclaimed)
	}
	return nil
}

func isStaleClaim(claimedAtStr string, now int64, visibility time.Duration) bool {
	if strings.TrimSpace(claimedAtStr) == "" {
		return true
	}
	var claimedAt int64
	if _, err := fmt.Sscan(claimedAtStr, &claimedAt); err != nil || claimedAt <= 0 {
		return true
	}
	return now-claimedAt > int64(visibility.Seconds())
}

func (c *Consumer) requeueOrDead(ctx context.Context, raw string, job *Job, reason string) {
	_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
	c.unclaim(ctx, job)
	next := job.Retries + 1
	if next > c.maxRetries {
		deadRaw, _ := json.Marshal(map[string]interface{}{"job": job, "error": reason})
		_ = c.redis.LPush(ctx, deadKey(), deadRaw).Err()
		c.logger.Error("stale job dead-lettered", "jobId", job.JobID, "type", job.Type, "error", reason)
		return
	}
	job.Retries = next
	retryRaw, _ := json.Marshal(job)
	_ = c.redis.LPush(ctx, QueueKeyLLM, retryRaw).Err()
	c.logger.Warn("stale job requeued", "jobId", job.JobID, "type", job.Type, "retries", job.Retries, "error", reason)
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
