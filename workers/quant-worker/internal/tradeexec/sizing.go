package tradeexec

import (
	"math"
	"strings"

	"github.com/shopspring/decimal"
)

var lotSize = map[string]int{"US": 1, "HK": 100, "CN": 100}

const (
	DailyListMaxPositionRatio = 0.15
	DailyListMaxNameNotional  = 8000.0
)

func LotForMarket(market string) int {
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if n, ok := lotSize[mkt]; ok {
		return n
	}
	return 1
}

// SizeDailyListOrder mirrors DailyListService._size_order (no FX; max of raw slices).
func SizeDailyListOrder(account Account, market string, rowPrice, quoteLast float64) int {
	net := 0.0
	for _, bal := range account.Balances {
		v := bal.NetAssets
		if v <= 0 {
			v = bal.AvailableCash
		}
		if v > net {
			net = v
		}
	}
	lot := LotForMarket(market)
	if net <= 0 {
		return lot
	}
	notional := math.Min(net*DailyListMaxPositionRatio, DailyListMaxNameNotional)
	price := rowPrice
	if price <= 0 {
		price = quoteLast
	}
	if price <= 0 {
		return lot
	}
	qty := int(notional / price)
	qty = max(lot, qty-(qty%lot))
	return qty
}

func BuyQuantityFromUSD(targetUSD, realtimePrice float64, market string, fx FxRates) int {
	if realtimePrice <= 0 {
		return 0
	}
	orderAmount := fx.FromUSD(targetUSD, fx.OrderCurrency(market))
	qty := int(orderAmount / realtimePrice)
	if qty < 1 {
		return 1
	}
	return qty
}

func ClampDailyBuyRatio(ratio float64) float64 {
	if math.IsNaN(ratio) || math.IsInf(ratio, 0) || ratio <= 0 {
		ratio = DailyBuyPositionRatio
	}
	if ratio < 0.05 {
		return 0.05
	}
	if ratio > 0.50 {
		return 0.50
	}
	return ratio
}

func MergeRuntimeConfig(custom map[string]interface{}) map[string]interface{} {
	cfg := map[string]interface{}{
		"enabled":                  true,
		"auto_execute":             false,
		"interval":                 900,
		"strategy_profile":         "balanced",
		"max_symbols":              3,
		"max_amount_per_symbol":    0.0,
		"max_daily_orders":         10,
		"max_daily_notional_amount": 0.0,
		"max_position_ratio":       DailyBuyPositionRatio,
		"max_symbol_position_pct":  DefaultMaxSymbolPositionPct,
		"min_confidence":           65,
		"price_slippage_tolerance": 0.03,
		"max_gross_exposure_pct":   MaxGrossExposurePct,
		"skip_held_buy":            true,
		"skip_cn":                  true,
	}
	allowed := map[string]struct{}{
		"max_symbols": {}, "min_confidence": {}, "strategy_profile": {}, "custom_thresholds": {},
	}
	for key, val := range custom {
		if _, ok := allowed[key]; ok && val != nil {
			cfg[key] = val
		}
	}
	cfg["max_symbols"] = clampInt(asInt(cfg["max_symbols"], 3), 1, 20)
	cfg["min_confidence"] = clampInt(asInt(cfg["min_confidence"], 65), 0, 100)
	return cfg
}

func asInt(v interface{}, fallback int) int {
	switch x := v.(type) {
	case int:
		return x
	case int64:
		return int(x)
	case float64:
		return int(x)
	case float32:
		return int(x)
	default:
		return fallback
	}
}

func clampInt(n, lo, hi int) int {
	if n < lo {
		return lo
	}
	if n > hi {
		return hi
	}
	return n
}

// RoundLimitPrice mirrors Python round_limit_price (HALF_UP to market tick).
func RoundLimitPrice(price float64, market string) float64 {
	if price <= 0 {
		return price
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	tick := "0.01"
	if mkt == "HK" {
		if price < 1 {
			tick = "0.001"
		}
	} else if price < 1 {
		tick = "0.0001"
	}
	tickD, _ := decimal.NewFromString(tick)
	priceD := decimal.NewFromFloat(price)
	steps := priceD.Div(tickD).Round(0)
	out, _ := steps.Mul(tickD).Float64()
	return out
}
