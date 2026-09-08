package jobqueue

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/sfp-backend/internal/jobs"
)

const (
	TicketTTLSeconds = 3600
	TicketKeyFmt     = "sfp:job:ticket:%s"
	TimeLayout       = "2006-01-02 15:04:05"
)

type Job struct {
	Type       string                 `json:"type"`
	Payload    map[string]interface{} `json:"payload"`
	JobID      string                 `json:"jobId"`
	Queue      string                 `json:"queue"`
	EnqueuedAt string                 `json:"enqueuedAt"`
}

type Enqueuer struct {
	redis *redis.Client
	loc   *time.Location
}

func New(rdb *redis.Client, loc *time.Location) *Enqueuer {
	if loc == nil {
		loc = time.Local
	}
	return &Enqueuer{redis: rdb, loc: loc}
}

func (e *Enqueuer) Enqueue(ctx context.Context, jobType string, payload map[string]interface{}) (Job, error) {
	if !jobs.NativeGoWorkerTypes[jobType] {
		return Job{}, fmt.Errorf("job type %s is not a native Go worker job", jobType)
	}
	if payload == nil {
		payload = map[string]interface{}{}
	}
	jobID := strings.ReplaceAll(uuid.NewString(), "-", "")
	job := Job{
		Type:       jobType,
		Payload:    payload,
		JobID:      jobID,
		Queue:      string(jobs.GroupFor(jobType)),
		EnqueuedAt: time.Now().In(e.loc).Format(TimeLayout),
	}
	raw, err := json.Marshal(job)
	if err != nil {
		return Job{}, err
	}
	key := jobs.QueueKey(jobs.GroupFor(jobType))
	if key == "" {
		return Job{}, fmt.Errorf("no queue for %s", jobType)
	}
	ticket := map[string]interface{}{
		"accepted": true, "jobId": jobID, "type": jobType, "queue": job.Queue,
		"status": "queued", "enqueuedAt": job.EnqueuedAt,
	}
	ticketRaw, err := json.Marshal(ticket)
	if err != nil {
		return Job{}, err
	}
	pipe := e.redis.TxPipeline()
	pipe.LPush(ctx, key, raw)
	pipe.Set(ctx, fmt.Sprintf(TicketKeyFmt, jobID), ticketRaw, time.Duration(TicketTTLSeconds)*time.Second)
	if _, err := pipe.Exec(ctx); err != nil {
		return Job{}, err
	}
	return job, nil
}
