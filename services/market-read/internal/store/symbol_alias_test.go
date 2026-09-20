package store

import (
	"database/sql"
	"testing"
)

func TestPriceSymbolAliasesHK(t *testing.T) {
	aliases := priceSymbolAliases("00700", "HK")
	want := map[string]bool{"00700": true, "0700.HK": true, "700": true}
	for item := range want {
		found := false
		for _, alias := range aliases {
			if alias == item {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("missing alias %s in %v", item, aliases)
		}
	}
}

func TestPriceSymbolAliasesDoesNotCrossMapShanghaiComposite(t *testing.T) {
	bare := priceSymbolAliases("000001", "CN")
	if containsAlias(bare, "000001.SH") || containsAlias(bare, "000001.SS") {
		t.Fatalf("bare 000001 must not alias 上证: %v", bare)
	}
	if !containsAlias(bare, "000001") {
		t.Fatalf("bare 000001 must keep itself: %v", bare)
	}
	sh := priceSymbolAliases("000001.SH", "CN")
	if containsAlias(sh, "000001") || containsAlias(sh, "000001.SZ") {
		t.Fatalf("000001.SH must not alias 平安银行: %v", sh)
	}
	if !containsAlias(sh, "000001.SH") {
		t.Fatalf("000001.SH must keep itself: %v", sh)
	}
	other := priceSymbolAliases("600519", "CN")
	for _, want := range []string{"600519", "600519.SH", "600519.SZ", "600519.SS"} {
		if !containsAlias(other, want) {
			t.Fatalf("other CN missing %s in %v", want, other)
		}
	}
}

func containsAlias(aliases []string, want string) bool {
	for _, a := range aliases {
		if a == want {
			return true
		}
	}
	return false
}

func TestMapClosesByAlias(t *testing.T) {
	mapped := mapClosesByAlias([]string{"00700"}, map[string]float64{"0700.HK": 320.5}, "HK")
	if mapped["00700"] != 320.5 {
		t.Fatalf("00700=%v", mapped["00700"])
	}
}

func TestCleanLastTreatsZeroAsMissing(t *testing.T) {
	if cleanLast(sql.NullFloat64{Float64: 0, Valid: true}) != nil {
		t.Fatal("zero last should be missing")
	}
	got := cleanLast(sql.NullFloat64{Float64: 191.2, Valid: true})
	if got != 191.2 {
		t.Fatalf("got %v", got)
	}
}
