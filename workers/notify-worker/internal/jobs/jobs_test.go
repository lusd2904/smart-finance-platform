package jobs

import (
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/newscollect"
)

func TestSourceReportsPreserveSkipAndError(t *testing.T) {
	out := sourceReports([]newscollect.SourceResult{
		{Source: "eastmoney", Fetched: 2},
		{Source: "x_monitor", Skipped: "ingest-only"},
		{Source: "ths", Error: "http 503"},
	})
	if len(out) != 3 {
		t.Fatalf("len=%d", len(out))
	}
	if out[1]["skipped"] != "ingest-only" {
		t.Fatalf("x_monitor skip lost: %v", out[1])
	}
	if out[2]["error"] != "http 503" {
		t.Fatalf("ths error lost: %v", out[2])
	}
}

func TestShouldAnalyzeFromPayloadDefaultsTrue(t *testing.T) {
	if !shouldAnalyzeFromPayload(nil) {
		t.Fatal("nil payload should analyze")
	}
	if !shouldAnalyzeFromPayload(map[string]interface{}{}) {
		t.Fatal("omitted analyze should analyze (job 100 empty job_kwargs)")
	}
	if !shouldAnalyzeFromPayload(map[string]interface{}{"analyze": nil}) {
		t.Fatal("null analyze should analyze")
	}
	if !shouldAnalyzeFromPayload(map[string]interface{}{"analyze": true}) {
		t.Fatal("explicit true should analyze")
	}
	if !shouldAnalyzeFromPayload(map[string]interface{}{"analyze": "true"}) {
		t.Fatal("string true should analyze")
	}
	if shouldAnalyzeFromPayload(map[string]interface{}{"analyze": false}) {
		t.Fatal("explicit false is collect-only")
	}
	if shouldAnalyzeFromPayload(map[string]interface{}{"analyze": "false"}) {
		t.Fatal("string false is collect-only")
	}
}

func TestShouldTryNextSentimentModel(t *testing.T) {
	cases := []struct {
		code int
		next bool
	}{
		{401, true},
		{402, true},
		{403, true},
		{408, true},
		{502, true},
		{503, true},
		{524, true},
		{529, true},
		{429, false},
		{400, false},
		{404, false},
		{500, false},
		{200, false},
		{0, false},
	}
	for _, tc := range cases {
		if got := shouldTryNextSentimentModel(tc.code); got != tc.next {
			t.Fatalf("code %d: got %v want %v", tc.code, got, tc.next)
		}
	}
}

func TestSentimentModelLoopContinuesPast401And402(t *testing.T) {
	codes := []int{401, 402, 200}
	tried := 0
	for _, code := range codes {
		tried++
		if code == 200 {
			break
		}
		if code == 429 || !shouldTryNextSentimentModel(code) {
			t.Fatalf("loop stopped early at %d after %d tries", code, tried)
		}
	}
	if tried != 3 {
		t.Fatalf("tried=%d want 3", tried)
	}
}

func TestSentimentModelLoopStopsOn429(t *testing.T) {
	tried := 0
	for _, code := range []int{429, 200} {
		tried++
		if code == 200 {
			t.Fatal("should not reach the next model after 429")
		}
		if code == 429 || !shouldTryNextSentimentModel(code) {
			break
		}
	}
	if tried != 1 {
		t.Fatalf("tried=%d want 1", tried)
	}
}

func TestOrderSentimentModelsPrefersGrok(t *testing.T) {
	ordered := orderSentimentModels([]aiModelRow{
		{ModelCode: "openai/gpt-4o-mini", Scope: "global"},
		{ModelCode: "x-ai/grok-4.6", Scope: "chat"},
		{ModelCode: "grok-4.6", Scope: "sentiment"},
	})
	if ordered[0].ModelCode != "grok-4.6" {
		t.Fatalf("preferred model should stay first, got %s", ordered[0].ModelCode)
	}
}

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
