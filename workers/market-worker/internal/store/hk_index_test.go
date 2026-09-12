package store

import (
	"os"
	"strings"
	"testing"
)

func TestFeaturedSymbolsHKIncludesHangSeng(t *testing.T) {
	got := featuredSymbols("HK")
	need := []string{"HSI", "HSTECH", "HSCEI", "0700.HK"}
	have := map[string]bool{}
	for _, s := range got {
		have[s] = true
	}
	for _, s := range need {
		if !have[s] {
			t.Fatalf("featuredSymbols(HK) missing %s: %v", s, got)
		}
	}
	if len(featuredSymbols("US")) == 0 || featuredSymbols("") != nil {
		t.Fatalf("US/empty featured changed unexpectedly")
	}
}

func TestMergeHKIndexInstrumentsAddsMissingAndSkipsAliases(t *testing.T) {
	usOnly := mergeHKIndexInstruments([]Instrument{{Symbol: "AAPL", Market: "US"}}, []string{"US"})
	if len(usOnly) != 1 {
		t.Fatalf("US universe must not grow HK indices: %+v", usOnly)
	}
	empty := mergeHKIndexInstruments(nil, []string{"HK"})
	if len(empty) != 3 {
		t.Fatalf("empty HK universe=%+v", empty)
	}
	for _, inst := range empty {
		if inst.Category != "index" || inst.Market != "HK" {
			t.Fatalf("merged row must be HK index: %+v", inst)
		}
	}
	existing := mergeHKIndexInstruments([]Instrument{
		{Symbol: "^HSI", Name: "alias", Market: "HK", Category: "listed"},
		{Symbol: "0700.HK", Market: "HK"},
	}, []string{"HK"})
	syms := map[string]bool{}
	for _, inst := range existing {
		syms[inst.Symbol] = true
	}
	if !syms["^HSI"] || syms["HSI"] {
		t.Fatalf("must treat ^HSI as already present, not duplicate HSI: %+v", existing)
	}
	if !syms["HSTECH"] || !syms["HSCEI"] || !syms["0700.HK"] {
		t.Fatalf("must add remaining indices and keep stock: %+v", existing)
	}
}

func TestMergeHKIndexBoardAndAssembleTreatsAsIndex(t *testing.T) {
	items := mergeHKIndexBoard([]instrumentRow{
		{Symbol: "0700.HK", Name: "腾讯", Market: "HK", Category: "stock"},
	})
	found := map[string]instrumentRow{}
	for _, inst := range items {
		found[inst.Symbol] = inst
	}
	for _, sym := range []string{"HSI", "HSTECH", "HSCEI"} {
		if found[sym].Category != "index" {
			t.Fatalf("%s missing from board universe: %+v", sym, items)
		}
	}
	quotes := assembleBoardQuotes([]instrumentRow{
		{Symbol: "HSI", Name: "恒生指数", Market: "HK", Category: "listed"},
	}, map[string][]dailyBar{
		"HSI": {{Date: "2026-09-11", Open: 1, High: 1, Low: 1, Close: 1, Volume: 1}},
	})
	if len(quotes) != 1 || quotes[0]["category"] != "index" {
		t.Fatalf("HSI listed category must still quote as index: %v", quotes)
	}
	if quotes[0]["source"] != "mysql" {
		t.Fatalf("HSI quote source=%v", quotes[0]["source"])
	}
}

func TestHKIndexSQLSeedIsIdempotent(t *testing.T) {
	body, err := os.ReadFile("../../../../sql/hk-index-instruments.sql")
	if err != nil {
		t.Fatal(err)
	}
	text := strings.ToLower(string(body))
	for _, frag := range []string{
		"insert into market_instrument",
		"'hsi'", "'hstech'", "'hscei'",
		"'hk'", "'index'",
		"on duplicate key update",
		"enabled = '1'",
	} {
		if !strings.Contains(text, frag) {
			t.Fatalf("hk-index-instruments.sql missing %q", frag)
		}
	}
	if strings.Contains(text, "drop table") || strings.Contains(text, "truncate") {
		t.Fatal("seed must not wipe market_instrument")
	}
}
