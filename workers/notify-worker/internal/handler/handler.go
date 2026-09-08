package handler

import (
	"context"
	"fmt"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/store"
)

var nativeJobs = map[string]bool{"feishu_push": true}

var delegateJobs = map[string]bool{
	"sentiment_collect": true, "sentiment_analyze": true, "watchlist_analyze": true,
	"daily_review": true, "req_send": true, "req_summarize": true, "stock_pick_run": true,
	"market_review": true, "ai_analyze": true, "ai_batch": true, "user_notice": true,
}

type Handler struct {
	store    *store.Service
	delegate *delegate.PythonClient
}

func New(store *store.Service, delegate *delegate.PythonClient) *Handler {
	return &Handler{store: store, delegate: delegate}
}

func (h *Handler) Handle(ctx context.Context, job queue.Job) (interface{}, error) {
	if nativeJobs[job.Type] {
		return h.store.RunFeishuPush(ctx)
	}
	if delegateJobs[job.Type] {
		return h.delegate.Run(ctx, job.Type, job.Payload)
	}
	return nil, fmt.Errorf("unsupported llm job type: %s", job.Type)
}
