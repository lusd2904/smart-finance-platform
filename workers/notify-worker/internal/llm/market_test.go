package llm

import "testing"

func TestRuleBasedMarketReview(t *testing.T) {
	result := RuleBasedMarketReview(map[string]interface{}{
		"marketLabel": "美股",
		"market":      "US",
		"tradeDate":   "2026-09-08",
		"benchmarks": []map[string]interface{}{
			{"name": "道指", "changeRate": 1.2, "changeText": "+1.20%"},
		},
		"upCount":     12,
		"downCount":   8,
		"sampleCount": 20,
		"news":        []map[string]interface{}{{"headline": "test"}},
		"sentiment":   []map[string]interface{}{},
	})
	if result["stance"] != "偏多" {
		t.Fatalf("expected bullish stance, got %v", result["stance"])
	}
	if result["score"] == nil {
		t.Fatal("expected score")
	}
}

func TestParseJSONObjectStripsCodeFence(t *testing.T) {
	parsed, err := parseJSONObject("```json\n{\"stance\":\"中性\",\"score\":50}\n```")
	if err != nil {
		t.Fatal(err)
	}
	if parsed["stance"] != "中性" {
		t.Fatalf("unexpected parse: %v", parsed)
	}
}
