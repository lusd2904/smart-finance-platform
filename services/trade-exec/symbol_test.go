package tradeexec

import "testing"

func TestToLongbridgeSymbol(t *testing.T) {
	cases := []struct{ symbol, market, want string }{
		{"AAPL", "US", "AAPL.US"},
		{"700", "HK", "700.HK"},
		{"600519", "CN", "600519.SH"},
		{"000858", "CN", "000858.SZ"},
		{"300750", "CN", "300750.SZ"},
		{"NVDA.US", "US", "NVDA.US"},
		{"^GSPC", "US", "^GSPC"},
		{"", "US", ""},
		{"aapl", "us", "AAPL.US"},
	}
	for _, c := range cases {
		got := ToLongbridgeSymbol(c.symbol, c.market)
		if got != c.want {
			t.Fatalf("ToLongbridgeSymbol(%q,%q)=%q want %q", c.symbol, c.market, got, c.want)
		}
	}
}

func TestParseSymbolMarket(t *testing.T) {
	code, mkt := ParseSymbolMarket("AAPL.US", "HK")
	if code != "AAPL" || mkt != "US" {
		t.Fatalf("got %s %s", code, mkt)
	}
	code, mkt = ParseSymbolMarket("600519.SH", "US")
	if code != "600519" || mkt != "CN" {
		t.Fatalf("got %s %s", code, mkt)
	}
	code, mkt = ParseSymbolMarket("00700.HK", "")
	if code != "00700" || mkt != "HK" {
		t.Fatalf("got %s %s", code, mkt)
	}
	code, mkt = ParseSymbolMarket("TSLA", "US")
	if code != "TSLA" || mkt != "US" {
		t.Fatalf("got %s %s", code, mkt)
	}
}

func TestSymbolMatchKeysIntersect(t *testing.T) {
	a := SymbolMatchKeys("00700.HK")
	b := SymbolMatchKeys("700")
	if !keysIntersect(a, b) {
		t.Fatal("00700.HK should match 700")
	}
	pos := []Position{{Symbol: "AAPL.US", Quantity: 10}}
	if MatchPosition(pos, "AAPL", "US") == nil {
		t.Fatal("expected AAPL match")
	}
	if MatchPosition(pos, "MSFT", "US") != nil {
		t.Fatal("did not expect MSFT match")
	}
}

func TestIsAutoTradeMarket(t *testing.T) {
	if !IsAutoTradeMarket("US", "AAPL") {
		t.Fatal("US should trade")
	}
	if !IsAutoTradeMarket("HK", "700") {
		t.Fatal("HK should trade")
	}
	if IsAutoTradeMarket("CN", "600519") {
		t.Fatal("CN should not auto-trade")
	}
	if IsAutoTradeMarket("US", "600519.SH") {
		t.Fatal("SH suffix should not auto-trade")
	}
}

func TestIsUSListed(t *testing.T) {
	if !IsUSListed("AAPL.US", "US") {
		t.Fatal()
	}
	if IsUSListed("700.HK", "HK") {
		t.Fatal()
	}
	if IsUSListed("600519.SH", "CN") {
		t.Fatal()
	}
}
