package jobqueue

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

const TicketTTLSeconds = 3600

const (
	QueueMarket = "sfp:job:queue:market"
	QueueQuant  = "sfp:job:queue:quant"
	QueueLLM    = "sfp:job:queue:llm"
)

var QueueKeys = map[string]string{
	"market": QueueMarket,
	"quant":  QueueQuant,
	"llm":    QueueLLM,
}

var JobGroups = map[string]string{
	"market_sync":         "market",
	"finance_briefings":   "market",
	"board_warmup":        "market",
	"symbol_content":      "market",
	"market_heat_collect": "market",
	"factor_scan":         "quant",
	"factor_qc":           "quant",
	"indicator_refresh":   "quant",
	"strategy_run":        "quant",
	"position_monitor":    "quant",
	"sentiment_collect":   "llm",
	"sentiment_analyze":   "llm",
	"watchlist_analyze":   "llm",
	"daily_review":        "llm",
	"req_send":            "llm",
	"req_summarize":       "llm",
	"daily_list_scan":     "quant",
	"daily_list_open":     "quant",
	"auto_trade_scan":     "quant",
	"feishu_push":         "llm",
	"stock_pick_run":      "llm",
	"eod_kline_sync":      "market",
	"market_review":       "llm",
	"ai_analyze":          "llm",
	"ai_batch":            "llm",
	"listings_sync":       "market",
	"klines_slow":         "market",
	"mysql_to_influx":     "market",
	"user_notice":         "llm",
}

var KnownJobs map[string]struct{}

func init() {
	KnownJobs = make(map[string]struct{}, len(JobGroups))
	for k := range JobGroups {
		KnownJobs[k] = struct{}{}
	}
}

type Queue struct {
	rdb *redis.Client
}

func New(rdb *redis.Client) *Queue {
	return &Queue{rdb: rdb}
}

func GroupFor(jobType string) string {
	if g, ok := JobGroups[jobType]; ok {
		return g
	}
	return "market"
}

func QueueKeyFor(jobType string) string {
	key := QueueKeys[GroupFor(jobType)]
	if key == "" {
		return QueueMarket
	}
	return key
}

func ticketKey(jobID string) string {
	return "sfp:job:ticket:" + jobID
}

type Job struct {
	Type       string                 `json:"type"`
	Payload    map[string]interface{} `json:"payload"`
	JobID      string                 `json:"jobId"`
	Queue      string                 `json:"queue"`
	EnqueuedAt string                 `json:"enqueuedAt"`
	Retries    int                    `json:"retries,omitempty"`
}

func Encode(jobType string, payload map[string]interface{}, jobID string) (string, error) {
	jobType = trim(jobType)
	if _, ok := KnownJobs[jobType]; !ok {
		return "", fmt.Errorf("未知任务类型: %s", jobType)
	}
	if jobID == "" {
		jobID = newJobID()
	}
	if payload == nil {
		payload = map[string]interface{}{}
	}
	job := Job{
		Type:       jobType,
		Payload:    payload,
		JobID:      jobID,
		Queue:      GroupFor(jobType),
		EnqueuedAt: time.Now().Format("2006-01-02 15:04:05"),
	}
	raw, err := json.Marshal(job)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

func Decode(raw string) (*Job, error) {
	if raw == "" {
		return nil, nil
	}
	var job Job
	if err := json.Unmarshal([]byte(raw), &job); err != nil {
		return nil, err
	}
	if _, ok := KnownJobs[job.Type]; !ok {
		return nil, errors.New("unknown job type")
	}
	return &job, nil
}

func TicketView(job *Job, status string) map[string]interface{} {
	if job == nil {
		return nil
	}
	return map[string]interface{}{
		"accepted":   true,
		"jobId":      job.JobID,
		"type":       job.Type,
		"queue":      firstNonEmpty(job.Queue, GroupFor(job.Type)),
		"status":     status,
		"enqueuedAt": job.EnqueuedAt,
	}
}

func (q *Queue) Submit(ctx context.Context, jobType string, payload map[string]interface{}) (map[string]interface{}, error) {
	if q.rdb == nil {
		return nil, errors.New("redis unavailable")
	}
	jobID := newJobID()
	raw, err := Encode(jobType, payload, jobID)
	if err != nil {
		return nil, err
	}
	job, err := Decode(raw)
	if err != nil {
		return nil, err
	}
	ticket := TicketView(job, "queued")
	ticketRaw, err := json.Marshal(ticket)
	if err != nil {
		return nil, err
	}
	pipe := q.rdb.Pipeline()
	pipe.LPush(ctx, QueueKeyFor(jobType), raw)
	pipe.SetEx(ctx, ticketKey(jobID), string(ticketRaw), TicketTTLSeconds*time.Second)
	if _, err := pipe.Exec(ctx); err != nil {
		return nil, err
	}
	return ticket, nil
}

func (q *Queue) GetTicket(ctx context.Context, jobID string) (map[string]interface{}, error) {
	if q.rdb == nil || jobID == "" {
		return nil, nil
	}
	raw, err := q.rdb.Get(ctx, ticketKey(jobID)).Result()
	if err == redis.Nil {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var ticket map[string]interface{}
	if err := json.Unmarshal([]byte(raw), &ticket); err != nil {
		return nil, nil
	}
	return ticket, nil
}

func trim(s string) string {
	for len(s) > 0 && (s[0] == ' ' || s[0] == '\t') {
		s = s[1:]
	}
	for len(s) > 0 && (s[len(s)-1] == ' ' || s[len(s)-1] == '\t') {
		s = s[:len(s)-1]
	}
	return s
}

func newJobID() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	return hex.EncodeToString(b[:])
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
