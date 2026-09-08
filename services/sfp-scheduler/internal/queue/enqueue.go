package queue

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/jobs"
)

const (
	TicketTTLSeconds = 3600
	TicketKeyFmt     = "sfp:job:ticket:%s"
	TimeLayout       = "2006-01-02 15:04:05"
)

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

func NewJobID() string {
	return strings.ReplaceAll(uuid.NewString(), "-", "")
}

func Encode(jobType string, payload map[string]any, loc *time.Location, jobID string) (string, Job, error) {
	if !jobs.KnownType(jobType) {
		return "", Job{}, fmt.Errorf("unknown job type: %s", jobType)
	}
	if payload == nil {
		payload = map[string]any{}
	}
	if loc == nil {
		loc = time.Local
	}
	if jobID == "" {
		jobID = NewJobID()
	}
	job := Job{
		Type:       jobType,
		Payload:    payload,
		JobID:      jobID,
		Queue:      string(jobs.GroupFor(jobType)),
		EnqueuedAt: time.Now().In(loc).Format(TimeLayout),
	}
	raw, err := json.Marshal(job)
	if err != nil {
		return "", Job{}, err
	}
	return string(raw), job, nil
}

func Decode(raw string) (*Job, error) {
	var job Job
	if err := json.Unmarshal([]byte(raw), &job); err != nil {
		return nil, err
	}
	if !jobs.KnownType(job.Type) {
		return nil, fmt.Errorf("unknown job type: %s", job.Type)
	}
	if job.Payload == nil {
		job.Payload = map[string]any{}
	}
	return &job, nil
}

type Enqueuer struct {
	redis *redis.Client
	loc   *time.Location
}

func NewEnqueuer(rdb *redis.Client, loc *time.Location) *Enqueuer {
	if loc == nil {
		loc = time.Local
	}
	return &Enqueuer{redis: rdb, loc: loc}
}

func (e *Enqueuer) Enqueue(ctx context.Context, spec jobs.Spec) (Job, error) {
	raw, job, err := Encode(spec.JobType, spec.Payload, e.loc, "")
	if err != nil {
		return Job{}, err
	}
	key := jobs.QueueKey(jobs.GroupFor(job.Type))
	if key == "" {
		return Job{}, fmt.Errorf("no queue key for %s", job.Type)
	}
	ticket := Ticket{
		Accepted:   true,
		JobID:      job.JobID,
		Type:       job.Type,
		Queue:      job.Queue,
		Status:     "queued",
		EnqueuedAt: job.EnqueuedAt,
	}
	ticketRaw, err := json.Marshal(ticket)
	if err != nil {
		return Job{}, err
	}
	pipe := e.redis.TxPipeline()
	pipe.LPush(ctx, key, raw)
	pipe.Set(ctx, fmt.Sprintf(TicketKeyFmt, job.JobID), ticketRaw, time.Duration(TicketTTLSeconds)*time.Second)
	if _, err := pipe.Exec(ctx); err != nil {
		return Job{}, err
	}
	return job, nil
}

func (e *Enqueuer) Depth(ctx context.Context) int64 {
	var total int64
	for _, key := range []string{
		jobs.QueueKey(jobs.QueueMarket),
		jobs.QueueKey(jobs.QueueQuant),
		jobs.QueueKey(jobs.QueueLLM),
	} {
		n, err := e.redis.LLen(ctx, key).Result()
		if err == nil {
			total += n
		}
	}
	return total
}
