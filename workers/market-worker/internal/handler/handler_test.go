package handler

import "testing"

func TestHeatAndContentAreNative(t *testing.T) {
	for _, jobType := range []string{"market_heat_collect", "symbol_content"} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s should be native", jobType)
		}
		if delegateJobs[jobType] {
			t.Fatalf("%s should not delegate to Python", jobType)
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
