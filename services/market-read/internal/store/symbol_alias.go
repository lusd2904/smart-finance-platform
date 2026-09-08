package store

import (
	"strings"
	"unicode"
)

func priceSymbolAliases(symbol, market string) []string {
	raw := strings.ToUpper(strings.TrimSpace(symbol))
	if raw == "" {
		return nil
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	base := raw
	if i := strings.LastIndex(raw, "."); i >= 0 {
		suffix := raw[i+1:]
		switch suffix {
		case "US", "HK", "SH", "SZ", "SS":
			base = raw[:i]
			if mkt == "" {
				if suffix == "US" {
					mkt = "US"
				} else if suffix == "HK" {
					mkt = "HK"
				} else {
					mkt = "CN"
				}
			}
		}
	}
	aliases := []string{raw, base}
	switch mkt {
	case "HK":
		digits := digitsOnly(base)
		if digits == "" {
			digits = base
		}
		stripped := strings.TrimLeft(digits, "0")
		if stripped == "" {
			stripped = "0"
		}
		aliases = append(aliases,
			base+".HK",
			digits,
			stripped,
			padLeft(stripped, 4),
			padLeft(stripped, 5),
			padLeft(stripped, 4)+".HK",
			padLeft(stripped, 5)+".HK",
		)
	case "CN":
		aliases = append(aliases, base+".SH", base+".SZ", base+".SS")
	case "US":
		aliases = append(aliases, base+".US")
	}
	out := make([]string, 0, len(aliases))
	seen := map[string]struct{}{}
	for _, item := range aliases {
		key := strings.ToUpper(strings.TrimSpace(item))
		if key == "" {
			continue
		}
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		out = append(out, key)
	}
	return out
}

func mapClosesByAlias(requested []string, found map[string]float64, market string) map[string]float64 {
	aliasToRequested := map[string]string{}
	for _, symbol := range requested {
		key := strings.ToUpper(strings.TrimSpace(symbol))
		if key == "" {
			continue
		}
		for _, alias := range priceSymbolAliases(key, market) {
			if _, ok := aliasToRequested[alias]; !ok {
				aliasToRequested[alias] = key
			}
		}
	}
	out := map[string]float64{}
	for dbSymbol, close := range found {
		if close <= 0 {
			continue
		}
		dbKey := strings.ToUpper(strings.TrimSpace(dbSymbol))
		target, ok := aliasToRequested[dbKey]
		if !ok {
			for _, alias := range priceSymbolAliases(dbKey, market) {
				if t, hit := aliasToRequested[alias]; hit {
					target = t
					ok = true
					break
				}
			}
		}
		if ok {
			if _, exists := out[target]; !exists {
				out[target] = close
			}
		}
	}
	return out
}

func digitsOnly(s string) string {
	var b strings.Builder
	for _, r := range s {
		if unicode.IsDigit(r) {
			b.WriteRune(r)
		}
	}
	return b.String()
}

func padLeft(s string, n int) string {
	if len(s) >= n {
		return s
	}
	return strings.Repeat("0", n-len(s)) + s
}
