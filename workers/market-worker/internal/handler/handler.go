package handler

import (
	"context"
	"fmt"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/queue"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/store"
)

// nativeJobs run entirely in Go without Python delegation.
var nativeJobs = map[string]bool{
	"market_sync":         true,
	"eod_kline_sync":      true,
	"klines_slow":         true,
	"mysql_to_influx":     true,
	"board_warmup":        true,
	"listings_sync":       true,
	"finance_briefings":   true,
	"market_heat_collect": true,
	"symbol_content":      true,
}

// delegateJobs is the leftover Python fallback list. Heat / symbol_content
// now run natively (public HTTP + Longbridge REST). Keep the map for future jobs.
var delegateJobs = map[string]bool{}

type Handler struct {
	store    *store.Service
	delegate *delegate.PythonClient
}

func New(store *store.Service, delegate *delegate.PythonClient) *Handler {
	return &Handler{store: store, delegate: delegate}
}

func (h *Handler) Handle(ctx context.Context, job queue.Job) (interface{}, error) {
	if nativeJobs[job.Type] {
		return h.handleNative(ctx, job)
	}
	if delegateJobs[job.Type] {
		return h.delegate.Run(ctx, job.Type, job.Payload)
	}
	return nil, fmt.Errorf("unsupported market job type: %s", job.Type)
}

func (h *Handler) handleNative(ctx context.Context, job queue.Job) (interface{}, error) {
	switch job.Type {
	case "market_sync":
		years := intFrom(job.Payload["years"], 10)
		symbol := stringFrom(job.Payload["symbol"])
		if symbol != "" {
			market := stringFrom(job.Payload["market"])
			if market == "" {
				market = "US"
			}
			pts, err := h.store.SyncSymbol(ctx, symbol, market, years)
			if err != nil {
				return nil, err
			}
			return map[string]interface{}{
				"synced_symbols": []string{symbol},
				"total_points":   pts,
				"details":        map[string]int{symbol: pts},
			}, nil
		}
		return h.store.SyncFeatured(ctx, years)
	case "eod_kline_sync":
		market := stringFrom(job.Payload["market"])
		if market == "" {
			market = "US"
		}
		years := intFrom(job.Payload["years"], 2)
		return h.store.SyncEODMarket(ctx, market, years)
	case "klines_slow":
		years := intFrom(job.Payload["years"], 10)
		return h.store.SyncUniverse(ctx, years)
	case "mysql_to_influx":
		symbol := stringFrom(job.Payload["symbol"])
		market := stringFrom(job.Payload["market"])
		if market == "" {
			market = "US"
		}
		return h.store.MySQLToInflux(ctx, symbol, market)
	case "board_warmup":
		return h.store.RefreshBoardQuotesCache(ctx)
	case "listings_sync":
		return h.store.SyncFromInflux(ctx)
	case "finance_briefings":
		return h.store.RefreshFinanceBriefings(ctx)
	case "market_heat_collect":
		market := stringFrom(job.Payload["market"])
		if market == "" {
			market = "US"
		}
		tradeDate := stringFrom(job.Payload["tradeDate"])
		if tradeDate == "" {
			tradeDate = stringFrom(job.Payload["trade_date"])
		}
		return h.store.CollectMarketHeat(ctx, market, tradeDate)
	case "symbol_content":
		return h.store.RefreshSymbolContent(ctx)
	default:
		return nil, fmt.Errorf("unhandled native job: %s", job.Type)
	}
}

func intFrom(v interface{}, fallback int) int {
	switch x := v.(type) {
	case float64:
		return int(x)
	case int:
		return x
	case string:
		var n int
		_, _ = fmt.Sscan(x, &n)
		if n > 0 {
			return n
		}
	}
	return fallback
}

func stringFrom(v interface{}) string {
	if v == nil {
		return ""
	}
	return fmt.Sprint(v)
}
