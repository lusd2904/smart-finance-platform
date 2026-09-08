package handler

import (
	"context"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/store"
)

// nativeJobs run entirely in Go (Influx + MySQL + Redis). No Python HTTP.
var nativeJobs = map[string]bool{
	"indicator_refresh": true,
	"factor_scan":       true,
	"factor_qc":         true,
	"strategy_run":      true,
	"daily_list_scan":   true,
	"position_monitor":  true,
}

// delegateJobs remain Python until #78 / P1 owns Longbridge order submit.
// Keep these off nativeJobs so the trade PR can claim them without a routing fight.
var delegateJobs = map[string]bool{
	"daily_list_open": true,
	"auto_trade_scan": true,
}

type Handler struct {
	store    *store.Service
	delegate *delegate.PythonClient
}

func New(store *store.Service, delegate *delegate.PythonClient) *Handler {
	return &Handler{store: store, delegate: delegate}
}

func NativeJobTypes() []string {
	return []string{"indicator_refresh", "factor_scan", "factor_qc", "strategy_run", "daily_list_scan", "position_monitor"}
}

func DeferredJobTypes() []string {
	return []string{"daily_list_open", "auto_trade_scan"}
}

func (h *Handler) Handle(ctx context.Context, job queue.Job) (interface{}, error) {
	if nativeJobs[job.Type] {
		return h.handleNative(ctx, job)
	}
	if delegateJobs[job.Type] {
		return h.delegate.Run(ctx, job.Type, job.Payload)
	}
	return nil, fmt.Errorf("unsupported quant job type: %s", job.Type)
}

func (h *Handler) handleNative(ctx context.Context, job queue.Job) (interface{}, error) {
	switch job.Type {
	case "indicator_refresh":
		return h.store.RunIndicatorRefresh(ctx)
	case "factor_scan":
		profile := stringFrom(job.Payload["profile"])
		if profile == "" {
			profile = "balanced"
		}
		return h.store.RunFactorScan(ctx, profile)
	case "factor_qc":
		market := strings.ToUpper(stringFrom(job.Payload["market"]))
		if market == "" {
			market = "US"
		}
		return h.store.RunFactorQC(ctx, market)
	case "strategy_run":
		return h.store.RunStrategy(ctx, job.Payload)
	case "daily_list_scan":
		return h.store.RunDailyListScan(ctx, job.Payload)
	case "position_monitor":
		return h.store.RunPositionMonitor(ctx)
	default:
		return nil, fmt.Errorf("unhandled native job: %s", job.Type)
	}
}

func stringFrom(v interface{}) string {
	if v == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(v))
}
