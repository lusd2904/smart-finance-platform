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
	QueueKeyQuant    = "sfp:job:queue:quant"
	ClaimsKey        = "sfp:job:claims"
	RunningKey       = "sfp:job:running"
	TicketTTLSeconds = 3600
	group            = "quant"
)

var quantJobTypes = map[string]bool{
	"factor_scan":       true,
	"factor_qc":         true,
	"indicator_refresh": true,
	"strategy_run":      true,
	"position_monitor":  true,
	"daily_list_scan":   true,
	"daily_list_open":   true,
	"auto_trade_scan":   true,
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
	return &Consumer{
		redis: rdb, handler: handler, visibilityTimeout: visibility, maxRetries: maxRetries,
		pollInterval: poll, reclaimInterval: reclaim, logger: logger,
	}
}

func decode(raw string) (*Job, error) {
	var job Job
	if err := json.Unmarshal([]byte(raw), &job); err != nil {
		return nil, err
	}
	if !quantJobTypes[job.Type] {
		return nil, fmt.Errorf("unknown job type: %s", job.Type)
	}
	if job.Payload == nil {
		job.Payload = map[string]interface{}{}
	}
	return &job, nil
}

func processingKey() string { return fmt.Sprintf("sfp:job:processing:%s", group) }
func deadKey() string         { return fmt.Sprintf("sfp:job:dead:%s", group) }

func (c *Consumer) Run(ctx context.Context) error {
	c.logger.Info("quant worker consumer started", "queue", QueueKeyQuant)
	nextReclaim := time.Now()
	for {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if time.Now().After(nextReclaim) {
			_ = c.recoverStale(ctx)
			nextReclaim = time.Now().Add(c.reclaimInterval)
		}
		raw, err := c.redis.RPopLPush(ctx, QueueKeyQuant, processingKey()).Result()
		if err == redis.Nil {
			time.Sleep(c.pollInterval)
			continue
		}
		if err != nil {
			time.Sleep(time.Second)
			continue
		}
		c.runOne(ctx, raw)
	}
}

func (c *Consumer) runOne(ctx context.Context, raw string) {
	job, err := decode(raw)
	if err != nil || job == nil {
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
		return
	}
	retries := job.Retries + 1
	if retries <= c.maxRetries {
		job.Retries = retries
		retryRaw, _ := json.Marshal(job)
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
		_ = c.redis.LPush(ctx, QueueKeyQuant, retryRaw).Err()
		c.writeTicket(ctx, job, "retrying", runErr.Error(), nil)
	} else {
		c.writeTicket(ctx, job, "failed", runErr.Error(), nil)
		deadRaw, _ := json.Marshal(map[string]interface{}{"job": job, "error": runErr.Error()})
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		_ = c.redis.HDel(ctx, ClaimsKey, job.JobID).Err()
		_ = c.redis.LPush(ctx, deadKey(), deadRaw).Err()
	}
	_ = c.redis.HDel(ctx, RunningKey, job.Type).Err()
}

func (c *Consumer) writeTicket(ctx context.Context, job *Job, status, errText string, result interface{}) {
	if job.JobID == "" {
		return
	}
	ticket := map[string]interface{}{"accepted": true, "jobId": job.JobID, "type": job.Type, "queue": group, "status": status}
	if errText != "" {
		ticket["error"] = errText
	}
	raw, _ := json.Marshal(ticket)
	_ = c.redis.SetEx(ctx, fmt.Sprintf("sfp:job:ticket:%s", job.JobID), raw, time.Duration(TicketTTLSeconds)*time.Second).Err()
}

func (c *Consumer) recoverStale(ctx context.Context) error {
	claims, _ := c.redis.HGetAll(ctx, ClaimsKey).Result()
	entries, _ := c.redis.LRange(ctx, processingKey(), 0, -1).Result()
	now := time.Now().Unix()
	for _, raw := range entries {
		job, err := decode(raw)
		if err != nil || job == nil {
			continue
		}
		var claimedAt int64
		_, _ = fmt.Sscan(claims[job.JobID], &claimedAt)
		if now-claimedAt <= int64(c.visibilityTimeout.Seconds()) {
			continue
		}
		_ = c.redis.LRem(ctx, processingKey(), 1, raw).Err()
		job.Retries++
		retryRaw, _ := json.Marshal(job)
		_ = c.redis.LPush(ctx, QueueKeyQuant, retryRaw).Err()
	}
	return nil
}

func (c *Consumer) QueueDepth(ctx context.Context) int64 {
	n, _ := c.redis.LLen(ctx, QueueKeyQuant).Result()
	return n
}

func Encode(jobType string, payload map[string]interface{}) (string, error) {
	if !quantJobTypes[jobType] {
		return "", fmt.Errorf("unknown job type: %s", jobType)
	}
	job := Job{
		Type: jobType, Payload: payload,
		JobID: strings.ReplaceAll(uuid.NewString(), "-", ""), Queue: group,
		EnqueuedAt: time.Now().Format("2006-01-02 15:04:05"),
	}
	raw, err := json.Marshal(job)
	return string(raw), err
}
