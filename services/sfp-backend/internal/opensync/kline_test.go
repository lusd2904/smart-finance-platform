package opensync

import (
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
)

func TestDailyPageToKlinesKeepsFluxShape(t *testing.T) {
	rows := []klineread.DailyPageRow{{
		Symbol: "AAPL", Market: "US", Date: "2026-09-11",
		Open: "100", High: "110", Low: "90", Close: "105", Volume: "1000",
	}}
	out := dailyPageToKlines(rows, "US")
	if len(out) != 1 {
		t.Fatalf("len=%d", len(out))
	}
	for _, key := range []string{"market", "symbol", "date", "open", "high", "low", "close", "volume"} {
		if _, ok := out[0][key]; !ok {
			t.Fatalf("missing %s", key)
		}
	}
	if out[0]["symbol"] != "AAPL" || out[0]["date"] != "2026-09-11" {
		t.Fatalf("row=%v", out[0])
	}
}

func TestDailyPageToKlinesEmpty(t *testing.T) {
	out := dailyPageToKlines(nil, "HK")
	if out == nil || len(out) != 0 {
		t.Fatalf("empty should be empty slice, got %v", out)
	}
}
