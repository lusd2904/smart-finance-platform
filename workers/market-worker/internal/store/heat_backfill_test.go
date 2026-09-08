package store

import (
	"context"
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
)

func TestBackfillTop50LastDryRunEmpty(t *testing.T) {
	// Requires MySQL in CI; skip when DB is unavailable.
	svc, err := NewMySQLOnly(testConfig())
	if err != nil {
		t.Skipf("mysql unavailable: %v", err)
	}
	defer svc.Close()

	result, err := svc.BackfillTop50Last(context.Background(), "US", "2099-01-01", "2099-01-02", true)
	if err != nil {
		t.Fatalf("backfill: %v", err)
	}
	if result["scanned"] != 0 {
		t.Fatalf("expected 0 scanned, got %v", result["scanned"])
	}
}

func testConfig() config.Config {
	return config.Load()
}
