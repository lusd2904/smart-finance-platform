package kline

import (
	"strings"
	"testing"
)

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

func TestVendorIndexAndTencentSymbol(t *testing.T) {
	cases := []struct {
		symbol, market, tencent, sina string
		ok                            bool
	}{
		{"HSI", "HK", "hkHSI", "HSI", true},
		{"HSTECH", "HK", "hkHSTECH", "HSTECH", true},
		{"HSCEI", "HK", "hkHSCEI", "HSCEI", true},
		{"HSI.HK", "HK", "hkHSI", "HSI", true},
		{"000001", "CN", "sh000001", "sh000001", true},
		{"000001.SH", "CN", "sh000001", "sh000001", true},
		{"399001", "CN", "sz399001", "sz399001", true},
		{"399006", "CN", "sz399006", "sz399006", true},
		{"^GSPC", "US", "usINX", ".INX", true},
		{"^DJI", "US", "usDJI", ".DJI", true},
		{"^IXIC", "US", "usIXIC", ".IXIC", true},
		{"000001.SZ", "CN", "", "", false},
		{"600519.SH", "CN", "", "", false},
		{"0700.HK", "HK", "", "", false},
		{"AAPL", "US", "", "", false},
	}
	for _, tc := range cases {
		tencent, sina, ok := VendorIndex(tc.symbol, tc.market)
		if ok != tc.ok || tencent != tc.tencent || sina != tc.sina {
			t.Fatalf("VendorIndex(%q,%q)=(%q,%q,%v) want (%q,%q,%v)",
				tc.symbol, tc.market, tencent, sina, ok, tc.tencent, tc.sina, tc.ok)
		}
		if tc.ok {
			if got := tencentSymbol(tc.symbol, tc.market); got != tc.tencent {
				t.Fatalf("tencentSymbol(%q,%q)=%q want %q", tc.symbol, tc.market, got, tc.tencent)
			}
			if got := sinaSymbol(tc.symbol, tc.market); got != tc.sina {
				t.Fatalf("sinaSymbol(%q,%q)=%q want %q", tc.symbol, tc.market, got, tc.sina)
			}
		}
	}
	if got := tencentSymbol("000001.SZ", "CN"); got != "sz000001" {
		t.Fatalf("bank 000001.SZ tencent=%q", got)
	}
	if got := tencentSymbol("000001", "CN"); got != "sh000001" {
		t.Fatalf("index 000001 tencent=%q", got)
	}
	if got := tencentSymbol("HSI", "HK"); got != "hkHSI" {
		t.Fatalf("HSI tencent=%q", got)
	}
	if got := tencentSymbol("^GSPC", "US"); got != "usINX" {
		t.Fatalf("^GSPC tencent=%q want usINX (not usGSPC)", got)
	}
}

func TestMinuteURLsUseHTTPS(t *testing.T) {
	for mkt, raw := range minuteURLs {
		if !strings.HasPrefix(raw, "https://") {
			t.Fatalf("%s minute URL must be https, got %s", mkt, raw)
		}
	}
	if !strings.Contains(minuteURLs["HK"], "hkMinute") {
		t.Fatalf("HK minute URL=%s", minuteURLs["HK"])
	}
	if !strings.Contains(minuteURLs["CN"], "/minute/query") {
		t.Fatalf("CN minute URL=%s", minuteURLs["CN"])
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
