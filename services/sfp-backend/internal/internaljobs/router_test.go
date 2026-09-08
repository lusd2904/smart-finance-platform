package internaljobs

import "testing"

func TestRouterTargets(t *testing.T) {
	r := New("secret", "http://intel:9099", "http://quant:9099", nil)
	if r.targetURL("sentiment_collect") != "" {
		t.Fatalf("llm jobs should enqueue via redis, not intel bridge")
	}
	if r.targetURL("strategy_evaluate") != "http://quant:9099/internal/jobs/run" {
		t.Fatalf("quant route mismatch")
	}
	empty := New("secret", "http://intel:9099", "", nil)
	if empty.targetURL("strategy_evaluate") != "" {
		t.Fatalf("empty strategy eval url should not delegate")
	}
	if r.targetURL("factor_scan") != "" {
		t.Fatalf("native quant job should not delegate")
	}
	if r.targetURL("market_heat_collect") != "" {
		t.Fatalf("native market job should not delegate")
	}
	if !r.IsKnown("factor_scan") {
		t.Fatalf("factor_scan should be known")
	}
	if !r.IsKnown("sentiment_collect") {
		t.Fatalf("sentiment_collect should be known")
	}
	if !r.IsKnown("req_send") {
		t.Fatalf("req_send should be known")
	}
}

func TestAuthorize(t *testing.T) {
	r := New("secret", "http://intel:9099", "http://quant:9099", nil)
	if !r.Authorize("secret") {
		t.Fatalf("expected authorized")
	}
	if r.Authorize("bad") {
		t.Fatalf("expected unauthorized")
	}
}
