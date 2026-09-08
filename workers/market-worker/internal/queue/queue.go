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
	QueueKeyMarket     = "sfp:job:queue:market"
	ClaimsKey          = "sfp:job:claims"
	RunningKey         = "sfp:job:running"
	TicketTTLSeconds   = 3600
	ProcessingKeyFmt   = "sfp:job:processing:%s"
	DeadKeyFmt         = "sfp:job:dead:%s"
	TicketKeyFmt       = "sfp:job:ticket:%s"
)

var marketJobTypes = map[string]bool{
	"market_sync":         true,
	"finance_briefings":   true,
	"board_warmup":        true,
	"symbol_content":      true,
	"market_heat_collect": true,
	"eod_kline_sync":      true,
	"listings_sync":       true,
	"klines_slow":         true,
	"mysql_to_influx":     true,
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
	redis              *redis.Client
	handler            Handler
	visibilityTimeout  time.Duration
	maxRetries         int
	pollInterval       time.Duration
	reclaimInterval    time.Duration
	logger             *slog.Logger
}

func NewConsumer(rdb *redis.Client, handler Handler, visibility time.Duration, maxRetries int, poll, reclaim time.Duration, logger *slog.Logger) *Consumer {
	return &Consumer{
		redis:             rdb,
		handler:           handler,
		visibilityTimeout: visibility,
		maxRetries:        maxRetries,
		pollInterval:      poll,
		reclaimInterval:   reclaim,
		logger:            logger,
	}
}

func Decode(raw string) (*Job, error) {
	var job Job
	if err := json.Unmarshal([]byte(raw), &job); err != nil {
		return nil, err
	}
	if !marketJobTypes[job.Type] {
		return nil, fmt.Errorf("unknown job type: %s", job.Type)
	}
	if job.Payload == nil {
		job.Payload = map[string]interface{}{}
	}
	return &job, nil
}

func Encode(jobType string, payload map[string]interface{}) (string, error) {
	if !marketJobTypes[jobType] {
		return "", fmt.Errorf("unknown job type: %s", jobType)
	}
	if payload == nil {
		payload = map[string]interface{}{}
	}
	job := Job{
		Type:       jobType,
		Payload:    payload,
		JobID:      strings.ReplaceAll(uuid.NewString(), "-", ""),
		Queue:      "market",
		EnqueuedAt: time.Now().Format("2006-01-02 15:04:05"),
	}
	raw, err := json.Marshal(job)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

func (c *Consumer) Run(ctx context.Context) error {
	c.logger.Info("market worker consumer started", "queue", QueueKeyMarket)
	nextReclaim := time.Now()
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if time.Now().After(nextReclaim) {
			if err := c.recoverStale(ctx); err != nil {
				c.logger.Warn("stale reclaim failed", "err", err)
			}
			nextReclaim = time.Now().Add(c.reclaimInterval)
		}
		raw, err := c.redis.RPopLPush(ctx, QueueKeyMarket, processingKey()).Result()
		if err == redis.Nil {
			time.Sleep(c.pollInterval)
			continue
		}
		if err != nil {
			c.logger.Warn("rpoplpush failed", "err", err)
			time.Sleep(time.Second)
			continue
		}
		c.runOne(ctx, raw)
	}
}

func processingKey() string {
	return fmt.Sprintf(ProcessingKeyFmt, "market")
}

func deadKey() string {
	return fmt.Sprintf(DeadKeyFmt, "market")
}

func (c *Consumer) runOne(ctx context.Context, raw string) {
	job, err := Decode(raw)
	if err != nil || job == nil {
		c.logger.Warn("dropping unparseable job")
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		return
	}
	_ = c.redis.HSet(ctx, ClaimsKey, job.JobID, time.Now().Unix()).Err()
	_ = c.redis.HSet(ctx, RunningKey, job.Type, time.Now().Format("2006-01-02 15:04:05")).Err()
	c.writeTicket(ctx, job, "running", "", nil)

	result, runErr := c.handler(ctx, *job)
	if runErr == nil {
		c.writeTicket(ctx, job, "done", "", result)
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
		_ = c.redis.HDel(ctx, RunningKey, job.Type).Err()
		c.logger.Info("job completed", "type", job.Type, "jobId", job.JobID)
		return
	}

	retries := job.Retries + 1
	if retries <= c.maxRetries {
		c.writeTicket(ctx, job, "retrying", runErr.Error(), nil)
		job.Retries = retries
		retryRaw, _ := json.Marshal(job)
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
		_ = c.redis.LPush(ctx, QueueKeyMarket, retryRaw).Err()
		c.logger.Warn("job will retry", "type", job.Type, "retries", retries, "err", runErr)
	} else {
		c.writeTicket(ctx, job, "failed", runErr.Error(), nil)
		dead := map[string]interface{}{
			"job":     job,
			"payload": job.Payload,
			"error":   truncate(runErr.Error(), 500),
			"retries": job.Retries,
			"failedAt": time.Now().Format("2006-01-02 15:04:05"),
		}
		deadRaw, _ := json.Marshal(dead)
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
		_ = c.redis.LPush(ctx, deadKey(), deadRaw).Err()
		c.logger.Error("job dead-lettered", "type", job.Type, "jobId", job.JobID, "err", runErr)
	}
	_ = c.redis.HDel(ctx, RunningKey, job.Type).Err()
}

func (c *Consumer) writeTicket(ctx context.Context, job *Job, status, errText string, result interface{}) {
	if job.JobID == "" {
		return
	}
	ticket := map[string]interface{}{
		"accepted":   true,
		"jobId":      job.JobID,
		"type":       job.Type,
		"queue":      "market",
		"status":     status,
		"enqueuedAt": job.EnqueuedAt,
	}
	if result != nil {
		ticket["resultPreview"] = truncate(fmt.Sprint(result), 240)
	}
	if errText != "" {
		ticket["error"] = truncate(errText, 500)
	}
	raw, _ := json.Marshal(ticket)
	key := fmt.Sprintf(TicketKeyFmt, job.JobID)
	_ = c.redis.SetEx(ctx, key, raw, time.Duration(TicketTTLSeconds)*time.Second).Err()
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
	for _, raw := range entries {
		job, err := Decode(raw)
		if err != nil || job == nil {
			continue
		}
		claimedAtStr := claims[job.JobID]
		if claimedAtStr == "" {
			_ = c.redis.HSet(ctx, ClaimsKey, job.JobID, now).Err()
			continue
		}
		var claimedAt int64
		_, _ = fmt.Sscan(claimedAtStr, &claimedAt)
		if now-claimedAt <= int64(c.visibilityTimeout.Seconds()) {
			continue
		}
		c.requeueOrDead(ctx, raw, job, "可见性超时回收（进程无响应）")
	}
	return nil
}

func (c *Consumer) requeueOrDead(ctx context.Context, raw string, job *Job, reason string) {
	_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
	_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
	next := job.Retries + 1
	if next > c.maxRetries {
		c.writeTicket(ctx, job, "failed", reason, nil)
		dead := map[string]interface{}{
			"job":     job,
			"payload": job.Payload,
			"error":   truncate(reason, 500),
			"retries": job.Retries,
			"failedAt": time.Now().Format("2006-01-02 15:04:05"),
		}
		deadRaw, _ := json.Marshal(dead)
		_ = c.redis.LPush(ctx, deadKey(), deadRaw).Err()
		return
	}
	job.Retries = next
	retryRaw, _ := json.Marshal(job)
	_ = c.redis.LPush(ctx, QueueKeyMarket, retryRaw).Err()
}

func (c *Consumer) QueueDepth(ctx context.Context) int64 {
	n, err := c.redis.LLen(ctx, QueueKeyMarket).Result()
	if err != nil {
		return 0
	}
	return n
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
