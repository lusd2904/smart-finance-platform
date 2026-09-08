package handler

import "testing"

func TestQuantNativeJobs(t *testing.T) {
	for _, jobType := range []string{
		"indicator_refresh", "factor_scan", "factor_qc",
		"strategy_run", "daily_list_scan", "position_monitor",
	} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s should be native", jobType)
		}
		if delegateJobs[jobType] {
			t.Fatalf("%s should not delegate to Python", jobType)
		}
	}
}

func TestP1JobsStillDelegated(t *testing.T) {
	for _, jobType := range []string{"daily_list_open", "auto_trade_scan"} {
		if nativeJobs[jobType] {
			t.Fatalf("%s is P1 order-submit and must stay delegated", jobType)
		}
		if !delegateJobs[jobType] {
			t.Fatalf("%s should remain on Python /internal/jobs/run until P1", jobType)
		}
	}
}
