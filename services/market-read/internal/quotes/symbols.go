package quotes

import (
	"strings"
)

const MaxLiveSymbols = 80

var markets = map[string]bool{"US": true, "HK": true, "CN": true}

type Pair struct {
	Symbol string
	Market string
}

func (p Pair) Key() string { return p.Symbol + "|" + p.Market }

func NormalizeSymbolMarket(symbol, market string) (Pair, bool) {
	raw := strings.ToUpper(strings.TrimSpace(symbol))
	if raw == "" {
		return Pair{}, false
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if mkt == "" {
		mkt = "US"
	}
	if strings.HasSuffix(raw, ".US") {
		raw, mkt = raw[:len(raw)-3], "US"
	} else if strings.HasSuffix(raw, ".HK") {
		raw, mkt = raw[:len(raw)-3], "HK"
	} else if strings.HasSuffix(raw, ".SS") || strings.HasSuffix(raw, ".SZ") || strings.HasSuffix(raw, ".SH") {
		raw = strings.SplitN(raw, ".", 2)[0]
		mkt = "CN"
	}
	if !markets[mkt] {
		mkt = "US"
	}
	if raw == "" {
		return Pair{}, false
	}
	return Pair{Symbol: raw, Market: mkt}, true
}

func ParseSubscribeSymbols(raw interface{}) []Pair {
	items, ok := raw.([]interface{})
	if !ok {
		return nil
	}
	pairs := make([]Pair, 0, len(items))
	seen := map[string]bool{}
	for _, item := range items {
		symbol := ""
		market := "US"
		switch v := item.(type) {
		case string:
			text := strings.TrimSpace(v)
			if i := strings.Index(text, ":"); i >= 0 {
				symbol, market = text[:i], text[i+1:]
			} else if i := strings.LastIndex(text, "."); i >= 0 {
				symbol, market = text[:i], text[i+1:]
			} else {
				symbol = text
			}
		case map[string]interface{}:
			symbol = stringify(v["symbol"])
			if m := stringify(v["market"]); m != "" {
				market = m
			}
		default:
			continue
		}
		pair, ok := NormalizeSymbolMarket(symbol, market)
		if !ok || seen[pair.Key()] {
			continue
		}
		seen[pair.Key()] = true
		pairs = append(pairs, pair)
		if len(pairs) >= MaxLiveSymbols {
			break
		}
	}
	return pairs
}

func ParseSymbolsQuery(raw string) []Pair {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return nil
	}
	parts := strings.Split(raw, ",")
	items := make([]interface{}, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			items = append(items, part)
		}
	}
	return ParseSubscribeSymbols(items)
}

func stringify(v interface{}) string {
	if v == nil {
		return ""
	}
	s, _ := v.(string)
	return s
}
