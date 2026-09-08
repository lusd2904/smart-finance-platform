package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"
)

const (
	queueLLM         = "sfp:job:queue:llm"
	ticketKeyFmt     = "sfp:job:ticket:%s"
	ticketTTLSeconds = 3600
	timeLayout       = "2006-01-02 15:04:05"
)

var jobGroups = map[string]string{
	"sentiment_collect": "llm",
	"sentiment_analyze": "llm",
	"req_send":          "llm",
	"req_summarize":     "llm",
}

type Enqueuer struct {
	redis *redis.Client
	loc   *time.Location
}

func NewEnqueuer(rdb *redis.Client) *Enqueuer {
	return &Enqueuer{redis: rdb, loc: time.Local}
}

type Job struct {
	Type       string         `json:"type"`
	Payload    map[string]any `json:"payload"`
	JobID      string         `json:"jobId"`
	Queue      string         `json:"queue"`
	EnqueuedAt string         `json:"enqueuedAt"`
}

type Ticket struct {
	Accepted   bool   `json:"accepted"`
	JobID      string `json:"jobId"`
	Type       string `json:"type"`
	Queue      string `json:"queue"`
	Status     string `json:"status"`
	EnqueuedAt string `json:"enqueuedAt"`
}

func (e *Enqueuer) Submit(ctx context.Context, jobType string, payload map[string]any) (*Ticket, error) {
	if _, ok := jobGroups[jobType]; !ok {
		return nil, fmt.Errorf("unknown job type: %s", jobType)
	}
	if payload == nil {
		payload = map[string]any{}
	}
	jobID := strings.ReplaceAll(uuid.NewString(), "-", "")
	now := time.Now().In(e.loc).Format(timeLayout)
	job := Job{
		Type: jobType, Payload: payload, JobID: jobID,
		Queue: jobGroups[jobType], EnqueuedAt: now,
	}
	raw, err := json.Marshal(job)
	if err != nil {
		return nil, err
	}
	ticket := &Ticket{
		Accepted: true, JobID: jobID, Type: jobType,
		Queue: jobGroups[jobType], Status: "queued", EnqueuedAt: now,
	}
	ticketRaw, err := json.Marshal(ticket)
	if err != nil {
		return nil, err
	}
	pipe := e.redis.TxPipeline()
	pipe.LPush(ctx, queueLLM, string(raw))
	pipe.Set(ctx, fmt.Sprintf(ticketKeyFmt, jobID), ticketRaw, ticketTTLSeconds*time.Second)
	if _, err := pipe.Exec(ctx); err != nil {
		return nil, err
	}
	return ticket, nil
}

func (e *Enqueuer) GetTicket(ctx context.Context, jobID string) (*Ticket, error) {
	raw, err := e.redis.Get(ctx, fmt.Sprintf(ticketKeyFmt, jobID)).Result()
	if err == redis.Nil {
		return nil, fmt.Errorf("任务不存在或已过期")
	}
	if err != nil {
		return nil, err
	}
	var ticket Ticket
	if err := json.Unmarshal([]byte(raw), &ticket); err != nil {
		return nil, err
	}
	return &ticket, nil
}
