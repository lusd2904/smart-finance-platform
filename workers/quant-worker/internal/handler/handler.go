package handler

import (
	"context"
	"fmt"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/store"
)

var nativeJobs = map[string]bool{
	"indicator_refresh": true,
}

var delegateJobs = map[string]bool{
	"factor_scan":       true,
	"factor_qc":         true,
	"strategy_run":      true,
	"position_monitor":  true,
	"daily_list_scan":   true,
	"daily_list_open":   true,
	"auto_trade_scan":   true,
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
		return h.store.RunIndicatorRefresh(ctx)
	}
	if delegateJobs[job.Type] {
		return h.delegate.Run(ctx, job.Type, job.Payload)
	}
	return nil, fmt.Errorf("unsupported quant job type: %s", job.Type)
}
