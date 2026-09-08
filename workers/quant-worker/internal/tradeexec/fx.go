package tradeexec

import (
	"math"
	"strings"
)

const (
	FallbackUSDHKD = 7.80
	FallbackUSDCNY = 7.20
)

type FxRates struct {
	USDHKD  float64
	USDCNY  float64
	Sources map[string]string
}

func NewFxRates() FxRates {
	return FxRates{
		USDHKD:  FallbackUSDHKD,
		USDCNY:  FallbackUSDCNY,
		Sources: map[string]string{"USDHKD": "fallback", "USDCNH": "fallback"},
	}
}

func NormalizeFxPairRate(symbol string, last float64) float64 {
	if last <= 0 {
		return 0
	}
	sym := strings.ToUpper(strings.TrimSpace(symbol))
	rate := last
	if last < 1 {
		rate = 1 / last
	}
	if sym == "HKDUSD" || sym == "CNHUSD" || sym == "CNYUSD" {
		if last >= 1 {
			return last
		}
		return 1 / last
	}
	return rate
}

func PickRateFromQuotes(quotes []Quote, pair string, fallback float64) (float64, string) {
	target := strings.ToUpper(pair)
	alt := ""
	if target == "USDCNH" {
		alt = "USDCNY"
	} else if target == "USDCNY" {
		alt = "USDCNH"
	}
	for _, q := range quotes {
		sym := strings.ToUpper(strings.ReplaceAll(q.Symbol, ".", ""))
		if sym != target && sym != alt {
			continue
		}
		last := q.LastDone
		if last == 0 {
			last = q.Last
		}
		parsed := NormalizeFxPairRate(sym, last)
		if parsed > 0 {
			return parsed, "longbridge"
		}
	}
	return fallback, "fallback"
}

func (f FxRates) ToUSD(amount float64, currency string) float64 {
	cur := strings.ToUpper(strings.TrimSpace(currency))
	if cur == "" {
		cur = "USD"
	}
	if amount == 0 {
		return 0
	}
	switch cur {
	case "USD", "US":
		return amount
	case "HKD":
		if f.USDHKD == 0 {
			return amount
		}
		return amount / f.USDHKD
	case "CNY", "CNH", "CN":
		if f.USDCNY == 0 {
			return amount
		}
		return amount / f.USDCNY
	default:
		return amount
	}
}

func (f FxRates) FromUSD(amountUSD float64, currency string) float64 {
	cur := strings.ToUpper(strings.TrimSpace(currency))
	if cur == "" {
		cur = "USD"
	}
	if amountUSD == 0 {
		return 0
	}
	switch cur {
	case "USD", "US":
		return amountUSD
	case "HKD":
		return amountUSD * f.USDHKD
	case "CNY", "CNH", "CN":
		return amountUSD * f.USDCNY
	default:
		return amountUSD
	}
}

func (f FxRates) OrderCurrency(market string) string {
	if strings.ToUpper(strings.TrimSpace(market)) == "HK" {
		return "HKD"
	}
	return "USD"
}

func (f FxRates) Snapshot() map[string]interface{} {
	src := f.Sources
	if src == nil {
		src = map[string]string{}
	}
	hkdSrc := src["USDHKD"]
	if hkdSrc == "" {
		hkdSrc = "fallback"
	}
	cnySrc := src["USDCNH"]
	if cnySrc == "" {
		cnySrc = "fallback"
	}
	return map[string]interface{}{
		"USDHKD":         math.Round(f.USDHKD*1e6) / 1e6,
		"USDCNH":         math.Round(f.USDCNY*1e6) / 1e6,
		"USDHKD_source":  hkdSrc,
		"USDCNH_source":  cnySrc,
	}
}

func SumBalanceFieldUSD(account Account, field string, fx FxRates, cashFallback bool) float64 {
	if len(account.Balances) == 0 {
		return 0
	}
	var total float64
	for _, row := range account.Balances {
		raw := 0.0
		switch field {
		case "netAssets":
			raw = row.NetAssets
		case "availableCash":
			raw = row.AvailableCash
		case "totalCash":
			raw = row.TotalCash
		}
		if raw == 0 && cashFallback {
			raw = row.AvailableCash
			if raw == 0 {
				raw = row.TotalCash
			}
		}
		total += fx.ToUSD(raw, row.Currency)
	}
	return math.Round(total*100) / 100
}

func PickNetAssets(account Account, fx FxRates) float64 {
	return SumBalanceFieldUSD(account, "netAssets", fx, true)
}

func PickAvailableCash(account Account, fx FxRates) float64 {
	return SumBalanceFieldUSD(account, "availableCash", fx, true)
}

func RawBalanceRows(account Account) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(account.Balances))
	for _, row := range account.Balances {
		avail := row.AvailableCash
		if avail == 0 {
			avail = row.TotalCash
		}
		net := row.NetAssets
		if net == 0 {
			net = avail
		}
		out = append(out, map[string]interface{}{
			"currency":      row.Currency,
			"totalCash":     row.TotalCash,
			"availableCash": avail,
			"netAssets":     net,
		})
	}
	return out
}

func AccountGuardrailSnapshot(account Account, fx FxRates) map[string]interface{} {
	return map[string]interface{}{
		"balanceByCurrency": RawBalanceRows(account),
		"netAssetsUsd":      PickNetAssets(account, fx),
		"availableCashUsd":  PickAvailableCash(account, fx),
		"fxRates":           fx.Snapshot(),
	}
}
