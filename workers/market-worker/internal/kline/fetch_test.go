package kline

import "testing"

func TestTradeDatePrefixShortAndEmpty(t *testing.T) {
	if d, ok := tradeDatePrefix(""); ok || d != "" {
		t.Fatalf("empty string: d=%q ok=%v", d, ok)
	}
	if d, ok := tradeDatePrefix("2024-"); ok || d != "" {
		t.Fatalf("len 5: d=%q ok=%v", d, ok)
	}
	if d, ok := tradeDatePrefix(nil); ok || d != "" {
		t.Fatalf("nil: d=%q ok=%v", d, ok)
	}
	got, ok := tradeDatePrefix("2024-06-01")
	if !ok || got != "2024-06-01" {
		t.Fatalf("valid date: d=%q ok=%v", got, ok)
	}
	got, ok = tradeDatePrefix("2024-06-01 15:04:05")
	if !ok || got != "2024-06-01" {
		t.Fatalf("datetime prefix: d=%q ok=%v", got, ok)
	}
}

func TestParseSinaBarsSkipsShortDates(t *testing.T) {
	arr := []interface{}{
		map[string]interface{}{"d": "2024-", "o": 1.0, "h": 2.0, "l": 1.0, "c": 1.5, "v": 10.0},
		map[string]interface{}{"d": "", "o": 1.0, "h": 2.0, "l": 1.0, "c": 1.5, "v": 10.0},
		map[string]interface{}{"d": "2024-06-01", "o": 1.0, "h": 2.0, "l": 1.0, "c": 1.5, "v": 10.0},
	}
	rows := parseSinaBars(arr, "AAPL", "US", "2020-01-01")
	if len(rows) != 1 {
		t.Fatalf("rows=%+v", rows)
	}
	if rows[0].TradeDate != "2024-06-01" || rows[0].Source != "sina" {
		t.Fatalf("row=%+v", rows[0])
	}
}

func TestParseTencentDailySkipsShortDates(t *testing.T) {
	payload := map[string]interface{}{
		"data": map[string]interface{}{
			"usAAPL": map[string]interface{}{
				"day": []interface{}{
					[]interface{}{"2024-", "1", "1.5", "2", "1", "10"},
					[]interface{}{"", "1", "1.5", "2", "1", "10"},
					[]interface{}{"2024-06-01", "1", "1.5", "2", "1", "10"},
				},
			},
		},
	}
	rows := parseTencentDaily(payload, "AAPL", "US", "2020-01-01")
	if len(rows) != 1 || rows[0].TradeDate != "2024-06-01" {
		t.Fatalf("rows=%+v", rows)
	}
}
