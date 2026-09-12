package store

import "testing"

func TestFeaturedSymbolsPinsMarketIndices(t *testing.T) {
	hk := featuredSymbols("HK")
	for _, want := range []string{"0700.HK", "9988.HK", "3690.HK", "HSI", "HSTECH", "HSCEI"} {
		if !containsSymbol(hk, want) {
			t.Fatalf("HK featured missing %s: %v", want, hk)
		}
	}
	cn := featuredSymbols("CN")
	for _, want := range []string{"600519.SH", "000001.SZ", "000001", "399001", "399006"} {
		if !containsSymbol(cn, want) {
			t.Fatalf("CN featured missing %s: %v", want, cn)
		}
	}
	if !containsSymbol(cn, "000001.SZ") {
		t.Fatal("000001.SZ (平安银行) must remain a featured stock")
	}
	if !containsSymbol(cn, "000001") {
		t.Fatal("000001 (上证指数) must be pinned as a featured CN index")
	}
}

func containsSymbol(list []string, want string) bool {
	for _, item := range list {
		if item == want {
			return true
		}
	}
	return false
}
