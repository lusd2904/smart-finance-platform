package tencent

import "testing"

func gtimgLine(code, name, last, prev, chgPct, ts string) string {
	parts := make([]string, 33)
	parts[1] = name
	parts[3] = last
	parts[4] = prev
	parts[30] = ts
	parts[32] = chgPct
	joined := ""
	for i, p := range parts {
		if i > 0 {
			joined += "~"
		}
		joined += p
	}
	return "v_" + code + "=\"" + joined + "\";"
}

func TestParseGtimgStockLine(t *testing.T) {
	text := gtimgLine("usAAPL", "苹果", "227.52", "226.01", "0.67", "2026-08-29 10:00:00")
	quotes := ParseGtimgText(text)
	q, ok := quotes["usAAPL"]
	if !ok {
		t.Fatal("missing usAAPL")
	}
	if q.Last == nil || *q.Last != 227.52 {
		t.Fatalf("last=%v", q.Last)
	}
	if q.PrevClose == nil || *q.PrevClose != 226.01 {
		t.Fatalf("prev=%v", q.PrevClose)
	}
	if q.ChangePct == nil || *q.ChangePct != 0.67 {
		t.Fatalf("chg=%v", q.ChangePct)
	}
	if q.Name != "苹果" {
		t.Fatalf("name=%q", q.Name)
	}
}

func TestParseGtimgSkipsShortLine(t *testing.T) {
	if got := ParseGtimgText(`v_usAAPL="a~b~c";`); len(got) != 0 {
		t.Fatalf("expected empty, got %v", got)
	}
}

func TestSymbolMapping(t *testing.T) {
	cases := []struct {
		symbol, market, want string
	}{
		{"AAPL", "US", "usAAPL"},
		{"00700", "HK", "hk00700"},
		{"700", "HK", "hk00700"},
		{"600519", "CN", "sh600519"},
		{"000001", "CN", "sz000001"},
		{"sh600519", "CN", "sh600519"},
		{"^GSPC", "US", "usGSPC"},
	}
	for _, tc := range cases {
		if got := Symbol(tc.symbol, tc.market); got != tc.want {
			t.Fatalf("Symbol(%q,%q)=%q want %q", tc.symbol, tc.market, got, tc.want)
		}
	}
}
