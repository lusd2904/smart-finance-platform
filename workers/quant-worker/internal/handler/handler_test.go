package handler

import (
	"context"
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/queue"
)

func TestAllQuantJobsAreNative(t *testing.T) {
	for _, jobType := range []string{
		"indicator_refresh",
		"factor_scan", "factor_qc", "strategy_run",
		"daily_list_scan", "position_monitor",
		"daily_list_open", "auto_trade_scan",
	} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s must be native; no Python container fallback exists", jobType)
		}
	}
}

func TestUnknownQuantJobDoesNotDelegate(t *testing.T) {
	h := &Handler{}
	_, err := h.Handle(context.Background(), queue.Job{Type: "missing_python_job"})
	if err == nil {
		t.Fatal("unknown jobs must fail locally")
	}
	if !strings.Contains(err.Error(), "unsupported quant job type") {
		t.Fatalf("expected unsupported job error, got %v", err)
	}
}

func TestNativeJobTypesListsBothSets(t *testing.T) {
	got := map[string]bool{}
	for _, jobType := range NativeJobTypes() {
		got[jobType] = true
	}
	for _, jobType := range []string{
		"factor_scan", "factor_qc", "strategy_run", "daily_list_scan",
		"position_monitor", "daily_list_open", "auto_trade_scan",
	} {
		if !got[jobType] {
			t.Fatalf("NativeJobTypes missing %s", jobType)
		}
	}
	if len(DeferredJobTypes()) != 0 {
		t.Fatalf("no jobs should remain deferred after #77+#78: %v", DeferredJobTypes())
	}
}
