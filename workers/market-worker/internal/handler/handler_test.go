package handler

import (
	"context"
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/queue"
)

func TestAllMarketJobsAreNative(t *testing.T) {
	for _, jobType := range []string{
		"market_sync", "eod_kline_sync", "klines_slow", "mysql_to_influx",
		"board_warmup", "listings_sync", "finance_briefings",
		"market_heat_collect", "symbol_content",
	} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s must be native; no Python container fallback exists", jobType)
		}
	}
	if len(NativeJobTypes()) != len(nativeJobs) {
		t.Fatalf("NativeJobTypes mismatch: %d vs %d", len(NativeJobTypes()), len(nativeJobs))
	}
}

func TestUnknownJobDoesNotDelegate(t *testing.T) {
	h := New(nil)
	_, err := h.Handle(context.Background(), queue.Job{Type: "strategy_evaluate"})
	if err == nil {
		t.Fatal("unknown jobs must fail locally")
	}
	if !strings.Contains(err.Error(), "unsupported market job type") {
		t.Fatalf("expected unsupported job error, got %v", err)
	}
}

func TestHeatAndContentAreNative(t *testing.T) {
	for _, jobType := range []string{"market_heat_collect", "symbol_content"} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s should be native", jobType)
		}
	}
}

func TestExistingNativeJobsUnchanged(t *testing.T) {
	for _, jobType := range []string{
		"market_sync", "eod_kline_sync", "klines_slow", "mysql_to_influx",
		"board_warmup", "listings_sync", "finance_briefings",
	} {
		if !nativeJobs[jobType] {
			t.Fatalf("regression: %s left native set", jobType)
		}
	}
}
