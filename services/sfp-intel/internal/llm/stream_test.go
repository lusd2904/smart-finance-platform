package llm

import "testing"

func TestUsageMetrics(t *testing.T) {
	m := usageMetrics(&usagePayload{PromptTokens: 10, CompletionTokens: 5, TotalTokens: 15})
	if m["inputTokens"] != 10 || m["outputTokens"] != 5 || m["totalTokens"] != 15 {
		t.Fatalf("unexpected metrics: %#v", m)
	}
}

func TestRunRegistryCancel(t *testing.T) {
	reg := NewRunRegistry()
	cancelled := false
	reg.Register("run1", func() { cancelled = true })
	if !reg.Cancel("run1") {
		t.Fatal("expected cancel ok")
	}
	if !cancelled {
		t.Fatal("cancel func not invoked")
	}
	if reg.Cancel("run1") {
		t.Fatal("second cancel should fail")
	}
}
