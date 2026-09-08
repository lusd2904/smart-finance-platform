package jobs

import "testing"

func TestFlattenPickAnalysis(t *testing.T) {
	flat := flattenPickAnalysis(map[string]interface{}{
		"ok": true, "symbol": "AAPL", "market": "US", "recommendation": "关注",
		"stance": "偏多", "confidence": 72, "summary": "test",
	})
	if flat["finalDecision"] != "关注" || flat["finalConfidence"] != 72 {
		t.Fatalf("unexpected flat: %v", flat)
	}
}

func TestNormalizeMarketReviewResult(t *testing.T) {
	fallback := map[string]interface{}{"stance": "中性", "score": 50, "title": "fallback"}
	out := normalizeMarketReviewResult(map[string]interface{}{
		"stance": "偏多", "score": 120, "title": "AI title",
	}, fallback)
	if out["stance"] != "偏多" {
		t.Fatalf("expected parsed stance")
	}
	if intFrom(out["score"]) != 100 {
		t.Fatalf("score should clamp to 100, got %v", out["score"])
	}
}

func TestStringSliceFrom(t *testing.T) {
	got := stringSliceFrom([]interface{}{"AAPL", "MSFT"})
	if len(got) != 2 || got[0] != "AAPL" {
		t.Fatalf("unexpected slice: %v", got)
	}
}
