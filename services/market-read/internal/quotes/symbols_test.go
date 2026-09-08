package quotes

import "testing"

func TestNormalizeSymbolSuffixes(t *testing.T) {
	pair, ok := NormalizeSymbolMarket("aapl.us", "HK")
	if !ok || pair != (Pair{Symbol: "AAPL", Market: "US"}) {
		t.Fatalf("got %+v ok=%v", pair, ok)
	}
	pair, ok = NormalizeSymbolMarket("00700.HK", "")
	if !ok || pair != (Pair{Symbol: "00700", Market: "HK"}) {
		t.Fatalf("got %+v ok=%v", pair, ok)
	}
	pair, ok = NormalizeSymbolMarket("600519.SS", "")
	if !ok || pair != (Pair{Symbol: "600519", Market: "CN"}) {
		t.Fatalf("got %+v ok=%v", pair, ok)
	}
	if _, ok = NormalizeSymbolMarket("", ""); ok {
		t.Fatal("empty should fail")
	}
}

func TestParseSubscribeMixedAndCap(t *testing.T) {
	pairs := ParseSubscribeSymbols([]interface{}{
		"AAPL:US",
		map[string]interface{}{"symbol": "00700", "market": "HK"},
		"AAPL.US",
		"MSFT",
	})
	want := []Pair{{"AAPL", "US"}, {"00700", "HK"}, {"MSFT", "US"}}
	if len(pairs) != len(want) {
		t.Fatalf("len=%d want %d: %#v", len(pairs), len(want), pairs)
	}
	for i := range want {
		if pairs[i] != want[i] {
			t.Fatalf("pairs[%d]=%+v want %+v", i, pairs[i], want[i])
		}
	}
	huge := make([]interface{}, 200)
	for i := 0; i < 200; i++ {
		huge[i] = "S" + itoa(i) + ":US"
	}
	if got := ParseSubscribeSymbols(huge); len(got) != MaxLiveSymbols {
		t.Fatalf("cap=%d", len(got))
	}
}

func TestParseSymbolsQuery(t *testing.T) {
	pairs := ParseSymbolsQuery("AAPL:US, 00700.HK")
	if len(pairs) != 2 || pairs[0] != (Pair{"AAPL", "US"}) || pairs[1] != (Pair{"00700", "HK"}) {
		t.Fatalf("%#v", pairs)
	}
	if ParseSymbolsQuery("") != nil {
		t.Fatal("empty query")
	}
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var b [8]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	return string(b[i:])
}
