package handler

import "testing"

func TestAllQuantJobsAreNative(t *testing.T) {
	for _, jobType := range []string{
		"indicator_refresh",
		"factor_scan", "factor_qc", "strategy_run",
		"daily_list_scan", "position_monitor",
		"daily_list_open", "auto_trade_scan",
	} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s should be native", jobType)
		}
		if delegateJobs[jobType] {
			t.Fatalf("%s should not delegate the whole job to Python", jobType)
		}
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
