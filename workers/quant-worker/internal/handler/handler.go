package handler

import (
	"context"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/jobs"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/store"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
	"github.com/redis/go-redis/v9"
)

// Combined native set after #77 + #78:
//
//	#77 — factor_scan, factor_qc, strategy_run, daily_list_scan
//	#78 — daily_list_open, auto_trade_scan, position_monitor (MO sell when auto_trade on)
var nativeJobs = map[string]bool{
	"indicator_refresh": true,
	"factor_scan":       true,
	"factor_qc":         true,
	"strategy_run":      true,
	"daily_list_scan":   true,
	"position_monitor":  true,
	"daily_list_open":   true,
	"auto_trade_scan":   true,
}

type Handler struct {
	store    *store.Service
	jobs     *jobs.Repo
	broker   tradeexec.Broker
	strategy jobs.StrategyClient
	rdb      *redis.Client
	reader   *influx.Reader
	keys     jobs.EncKeys
}

func New(storeSvc *store.Service, repo *jobs.Repo, broker tradeexec.Broker, strategy jobs.StrategyClient, rdb *redis.Client, reader *influx.Reader, cfg config.Config) *Handler {
	return &Handler{
		store: storeSvc, jobs: repo, broker: broker, strategy: strategy, rdb: rdb, reader: reader,
		keys: jobs.EncKeys{CredentialKey: cfg.CredentialKey, JWTSecret: cfg.JWTSecret, AppEnv: cfg.AppEnv},
	}
}

func NativeJobTypes() []string {
	return []string{
		"indicator_refresh", "factor_scan", "factor_qc", "strategy_run",
		"daily_list_scan", "position_monitor", "daily_list_open", "auto_trade_scan",
	}
}

func DeferredJobTypes() []string {
	return nil
}

func (h *Handler) Handle(ctx context.Context, job queue.Job) (interface{}, error) {
	if nativeJobs[job.Type] {
		return h.handleNative(ctx, job)
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
		return jobs.RunPositionMonitor(ctx, h.jobs, h.broker, h.rdb, h.keys, h.klineClose)
	case "daily_list_open":
		return jobs.RunDailyListOpen(ctx, h.jobs, h.broker, h.rdb, h.keys)
	case "auto_trade_scan":
		return jobs.RunAutoTradeScan(ctx, h.jobs, h.broker, h.strategy, h.rdb, h.keys, job.Payload)
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

func (h *Handler) klineClose(ctx context.Context, market string, symbols []string) (map[string]float64, error) {
	out := map[string]float64{}
	if h.reader == nil {
		return out, nil
	}
	grouped, err := h.reader.QueryLatestKlines(ctx, market, symbols, 1, "-30d")
	if err != nil {
		return out, err
	}
	for _, sym := range symbols {
		bars := grouped[sym]
		if len(bars) == 0 {
			continue
		}
		out[sym] = bars[len(bars)-1].Close
	}
	return out, nil
}
