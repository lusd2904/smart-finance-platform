package jobs

import (
	"strings"
	"testing"
)

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
	if BridgeLabel("strategy_evaluate") != "internal-jobs" {
		t.Fatalf("expected internal-jobs hop for strategy_evaluate")
	}
	if BridgeLabel("factor_scan") != "redis-go-worker" {
		t.Fatalf("expected redis worker")
	}
}

func TestNoJobTypeRequiresPythonContainer(t *testing.T) {
	if len(IntelBridgeTypes) != 0 {
		t.Fatalf("IntelBridgeTypes must stay empty (no Python intel container): %v", IntelBridgeTypes)
	}
	pythonHints := []string{"python", "sentiment-data", "sentiment-backend", "sentiment-intel", "sentiment-trade"}
	check := func(jobType, label string) {
		lower := strings.ToLower(label)
		for _, hint := range pythonHints {
			if strings.Contains(lower, hint) {
				t.Fatalf("%s label %q implies a Python container", jobType, label)
			}
		}
	}
	for jobType := range NativeGoWorkerTypes {
		check(jobType, BridgeLabel(jobType))
	}
	for jobType := range QuantBridgeTypes {
		label := BridgeLabel(jobType)
		check(jobType, label)
		if label != "internal-jobs" {
			t.Fatalf("%s should be an internal-jobs hop, got %q", jobType, label)
		}
	}
}

func TestKnownWorkerJobsAreNative(t *testing.T) {
	for jobType, queue := range jobGroups {
		if !NativeGoWorkerTypes[jobType] {
			t.Fatalf("%s on %s queue is not native; no Python container fallback exists", jobType, queue)
		}
	}
}
