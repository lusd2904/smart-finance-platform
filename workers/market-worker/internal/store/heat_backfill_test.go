package store

import "testing"

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

func TestMapClosesByAlias(t *testing.T) {
	mapped := mapClosesByAlias(
		[]string{"00700", "AAPL"},
		map[string]float64{"0700.HK": 320.5, "AAPL.US": 191.2},
		"HK",
	)
	if mapped["00700"] != 320.5 {
		t.Fatalf("00700=%v", mapped["00700"])
	}
	mappedUS := mapClosesByAlias([]string{"AAPL"}, map[string]float64{"AAPL.US": 191.2}, "US")
	if mappedUS["AAPL"] != 191.2 {
		t.Fatalf("AAPL=%v", mappedUS["AAPL"])
	}
}
