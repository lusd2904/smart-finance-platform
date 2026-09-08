package tradeexec

import (
	"strings"
)

// ParseSymbolMarket splits AAPL.US / 00700.HK / 600519.SH into (code, market).
// SH/SZ suffixes map to CN. Bare codes keep defaultMarket (US if empty).
func ParseSymbolMarket(raw, defaultMarket string) (code, market string) {
	text := strings.ToUpper(strings.TrimSpace(raw))
	if defaultMarket == "" {
		defaultMarket = "US"
	}
	defaultMarket = strings.ToUpper(strings.TrimSpace(defaultMarket))
	if i := strings.LastIndex(text, "."); i > 0 {
		suffix := text[i+1:]
		switch suffix {
		case "US", "HK":
			return text[:i], suffix
		case "SH", "SZ":
			return text[:i], "CN"
		}
	}
	return text, defaultMarket
}

// ToLongbridgeSymbol mirrors Python LongbridgeService.to_longbridge_symbol.
func ToLongbridgeSymbol(symbol, market string) string {
	raw := strings.ToUpper(strings.TrimSpace(symbol))
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if raw == "" {
		return raw
	}
	if strings.Contains(raw, ".") || strings.HasPrefix(raw, "^") {
		return raw
	}
	if mkt == "" {
		mkt = "US"
	}
	suffix := mkt
	switch mkt {
	case "US":
		suffix = "US"
	case "HK":
		suffix = "HK"
	case "CN":
		suffix = "SH"
		if isDigits(raw) && !strings.HasPrefix(raw, "6") {
			suffix = "SZ"
		}
	}
	return raw + "." + suffix
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

// SymbolMatchKeys normalizes AAPL.US / 00700.HK / 700 into overlapping keys.
func SymbolMatchKeys(symbol string) map[string]struct{} {
	raw := strings.ToUpper(strings.TrimSpace(symbol))
	out := map[string]struct{}{}
	if raw == "" {
		return out
	}
	add := func(k string) {
		if k != "" {
			out[k] = struct{}{}
		}
	}
	add(raw)
	if i := strings.LastIndex(raw, "."); i > 0 {
		code, suffix := raw[:i], raw[i+1:]
		add(code)
		if isDigits(code) {
			stripped := strings.TrimLeft(code, "0")
			if stripped == "" {
				stripped = "0"
			}
			add(stripped)
			add(stripped + "." + suffix)
		}
	} else if isDigits(raw) {
		stripped := strings.TrimLeft(raw, "0")
		if stripped == "" {
			stripped = "0"
		}
		add(stripped)
	}
	return out
}

func keysIntersect(a, b map[string]struct{}) bool {
	for k := range a {
		if _, ok := b[k]; ok {
			return true
		}
	}
	return false
}

// MatchPosition finds a Longbridge position row for symbol/market.
func MatchPosition(positions []Position, symbol, market string) *Position {
	lb := ToLongbridgeSymbol(symbol, market)
	keys := SymbolMatchKeys(symbol)
	for k := range SymbolMatchKeys(lb) {
		keys[k] = struct{}{}
	}
	for k := range SymbolMatchKeys(symbol + "." + market) {
		keys[k] = struct{}{}
	}
	if len(keys) == 0 {
		return nil
	}
	for i := range positions {
		if keysIntersect(keys, SymbolMatchKeys(positions[i].Symbol)) {
			p := positions[i]
			return &p
		}
	}
	return nil
}

func IsCNMarket(market, symbol string) bool {
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if mkt == "CN" || mkt == "SH" || mkt == "SZ" || mkt == "A" {
		return true
	}
	raw := strings.ToUpper(strings.TrimSpace(symbol))
	return strings.HasSuffix(raw, ".SH") || strings.HasSuffix(raw, ".SZ")
}

func IsAutoTradeMarket(market, symbol string) bool {
	if IsCNMarket(market, symbol) {
		return false
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if mkt == "CN" || mkt == "SH" || mkt == "SZ" || mkt == "A" {
		return false
	}
	return mkt == "US" || mkt == "HK" || mkt == ""
}

func IsUSListed(lbSymbol, market string) bool {
	raw := strings.ToUpper(strings.TrimSpace(lbSymbol))
	if strings.HasSuffix(raw, ".HK") || strings.HasSuffix(raw, ".SH") || strings.HasSuffix(raw, ".SZ") || strings.HasSuffix(raw, ".CN") {
		return false
	}
	if strings.HasSuffix(raw, ".US") {
		return true
	}
	return strings.ToUpper(strings.TrimSpace(market)) == "US"
}
