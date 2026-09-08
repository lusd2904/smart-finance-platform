package jobs

import "testing"

func TestNativeJobsNotDelegated(t *testing.T) {
	for jobType := range NativeGoWorkerTypes {
		if IntelBridgeTypes[jobType] || QuantBridgeTypes[jobType] {
			t.Fatalf("%s should not be a bridge job", jobType)
		}
	}
}

func TestBridgeLabels(t *testing.T) {
	if BridgeLabel("sentiment_collect") != "redis-go-worker" {
		t.Fatalf("expected redis worker for sentiment_collect")
	}
	if BridgeLabel("strategy_evaluate") != "sentiment-data" {
		t.Fatalf("expected quant bridge")
	}
	if BridgeLabel("factor_scan") != "redis-go-worker" {
		t.Fatalf("expected redis worker")
	}
}
