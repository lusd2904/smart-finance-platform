package handler

import (
	"context"
	"fmt"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/jobs"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/store"
)

var nativeJobs = map[string]bool{
	"feishu_push": true,
	"user_notice": true,
	"sentiment_collect": true, "sentiment_analyze": true, "daily_review": true,
	"req_send": true, "req_summarize": true,
	"watchlist_analyze": true, "stock_pick_run": true, "market_review": true,
	"ai_analyze": true, "ai_batch": true,
}

type Handler struct {
	store *store.Service
	jobs  *jobs.Service
}

func New(store *store.Service, jobsSvc *jobs.Service) *Handler {
	return &Handler{store: store, jobs: jobsSvc}
}

func NativeJobTypes() []string {
	out := make([]string, 0, len(nativeJobs))
	for t := range nativeJobs {
		out = append(out, t)
	}
	return out
}

func DeferredJobTypes() []string {
	return []string{"watchlist_analyze", "stock_pick_run", "market_review", "ai_analyze", "ai_batch"}
}

func (h *Handler) Handle(ctx context.Context, job queue.Job) (interface{}, error) {
	if !nativeJobs[job.Type] {
		return nil, fmt.Errorf("unsupported llm job type: %s", job.Type)
	}
	if job.Type == "feishu_push" {
		return h.store.RunFeishuPush(ctx)
	}
	return h.jobs.Handle(ctx, job.Type, job.Payload)
}
