package internaljobs

import "testing"

func TestRouterTargets(t *testing.T) {
	r := New("secret", "http://intel:9099", "http://quant:9099")
	if r.targetURL("sentiment_collect") != "http://intel:9099/internal/jobs/run" {
		t.Fatalf("intel route mismatch")
	}
	if r.targetURL("strategy_evaluate") != "http://quant:9099/internal/jobs/run" {
		t.Fatalf("quant route mismatch")
	}
	if r.targetURL("unknown_job") != "" {
		t.Fatalf("expected empty for unknown")
	}
}

func TestAuthorize(t *testing.T) {
	r := New("secret", "http://intel:9099", "http://quant:9099")
	if !r.Authorize("secret") {
		t.Fatalf("expected authorized")
	}
	if r.Authorize("bad") {
		t.Fatalf("expected unauthorized")
	}
}
