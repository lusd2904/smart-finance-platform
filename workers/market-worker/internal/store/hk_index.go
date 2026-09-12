package store

import "strings"

// Hang Seng family always belongs on board_warmup / eod universe even when
// market_instrument is missing the rows or listed them as category=listed.
var hkIndexUniverse = []struct {
	Symbol   string
	Name     string
	Market   string
	Category string
}{
	{Symbol: "HSI", Name: "恒生指数", Market: "HK", Category: "index"},
	{Symbol: "HSTECH", Name: "恒生科技指数", Market: "HK", Category: "index"},
	{Symbol: "HSCEI", Name: "恒生中国企业指数", Market: "HK", Category: "index"},
}

func canonicalHKIndexSymbol(symbol string) string {
	s := strings.ToUpper(strings.TrimSpace(symbol))
	s = strings.TrimSuffix(s, ".HK")
	return strings.TrimPrefix(s, "^")
}

func isHKIndexSymbol(symbol string) bool {
	switch canonicalHKIndexSymbol(symbol) {
	case "HSI", "HSTECH", "HSCEI":
		return true
	}
	return false
}

func marketIncludesHK(markets []string) bool {
	if len(markets) == 0 {
		return true
	}
	for _, m := range markets {
		if strings.EqualFold(strings.TrimSpace(m), "HK") {
			return true
		}
	}
	return false
}

func mergeHKIndexInstruments(items []Instrument, markets []string) []Instrument {
	if !marketIncludesHK(markets) {
		return items
	}
	have := map[string]bool{}
	for _, item := range items {
		have[canonicalHKIndexSymbol(item.Symbol)] = true
	}
	for _, idx := range hkIndexUniverse {
		if have[idx.Symbol] {
			continue
		}
		items = append(items, Instrument{
			Symbol: idx.Symbol, Name: idx.Name, Market: idx.Market, Category: idx.Category,
		})
	}
	return items
}

func mergeHKIndexBoard(items []instrumentRow) []instrumentRow {
	have := map[string]bool{}
	for _, item := range items {
		have[canonicalHKIndexSymbol(item.Symbol)] = true
	}
	for _, idx := range hkIndexUniverse {
		if have[idx.Symbol] {
			continue
		}
		items = append(items, instrumentRow{
			Symbol: idx.Symbol, Name: idx.Name, Market: idx.Market, Category: idx.Category,
		})
	}
	return items
}
