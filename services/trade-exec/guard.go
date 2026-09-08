package tradeexec

import (
	"fmt"
	"math"
	"strings"
)

var (
	buySides  = map[string]struct{}{"buy": {}, "b": {}, "买": {}, "买入": {}}
	sellSides = map[string]struct{}{"sell": {}, "s": {}, "卖": {}, "卖出": {}}
	skipOrder = map[string]struct{}{
		"cancelled": {}, "canceled": {}, "rejected": {}, "expired": {}, "failed": {},
	}
)

func NormalizeSide(side string) string {
	text := strings.ToLower(strings.TrimSpace(side))
	if _, ok := buySides[text]; ok {
		return "buy"
	}
	if _, ok := sellSides[text]; ok {
		return "sell"
	}
	return text
}

func IsBuySide(side string) bool { return NormalizeSide(side) == "buy" }

func OrderNotional(quantity, price float64) float64 {
	if math.IsNaN(quantity) || math.IsInf(quantity, 0) || math.IsNaN(price) || math.IsInf(price, 0) {
		return 0
	}
	if quantity <= 0 || price <= 0 {
		return 0
	}
	return math.Round(quantity*price*100) / 100
}

func TodayBuyNotionalFromOrders(orders []Order) (count int, notional float64) {
	for _, row := range orders {
		status := strings.ToLower(strings.ReplaceAll(row.Status, " ", "_"))
		if _, skip := skipOrder[status]; skip {
			continue
		}
		count++
		if !IsBuySide(row.Side) {
			continue
		}
		qty := row.Quantity
		if qty <= 0 {
			qty = row.ExecutedQuantity
		}
		price := row.Price
		if price <= 0 {
			price = row.ExecutedPrice
		}
		if qty > 0 && price > 0 {
			notional += qty * price
		}
	}
	return count, math.Round(notional*100) / 100
}

func DailyBuyCap(netAssets, ratio float64) float64 {
	assets := math.Max(0, netAssets)
	return math.Round(assets*ratio*100) / 100
}

const DefaultMaxSymbolPositionPct = 0.10

func ClampMaxSymbolPositionPct(pct float64) float64 {
	if math.IsNaN(pct) || math.IsInf(pct, 0) {
		pct = DefaultMaxSymbolPositionPct
	}
	if pct < 0.05 {
		return 0.05
	}
	if pct > 0.30 {
		return 0.30
	}
	return pct
}

func SymbolPositionCap(netAssets, pct float64) float64 {
	assets := math.Max(0, netAssets)
	return math.Round(assets*ClampMaxSymbolPositionPct(pct)*100) / 100
}

func SymbolBuyRoom(netAssets, pct, existingMV float64) float64 {
	held := existingMV
	if math.IsNaN(held) || held < 0 {
		held = 0
	}
	return math.Round((SymbolPositionCap(netAssets, pct)-held)*100) / 100
}

const MaxGrossExposurePct = 1.0

func RemainingGrossRoom(netAssets, totalMV, maxPct float64) float64 {
	if maxPct <= 0 {
		maxPct = 0
	}
	cap := math.Max(0, netAssets) * maxPct
	held := math.Max(0, totalMV)
	return math.Round((cap-held)*100) / 100
}

func BuyBlockedReason(notional, netAssets, availableCash, totalMV, existingMV, todayNotional, dailyBuyRatio, maxSymbolPct float64) string {
	if notional <= 0 {
		return "无法估算买入金额（需要有效价格与数量）"
	}
	if netAssets <= 0 {
		return "账户净资产为 0，无法计算仓位上限"
	}
	maxDaily := DailyBuyCap(netAssets, dailyBuyRatio)
	remainingDaily := math.Max(0, maxDaily-math.Max(0, todayNotional))
	if notional > remainingDaily+1e-6 {
		return fmt.Sprintf("超过日内买入上限：本单 $%.2f，剩余 $%.2f（净资产 %d%% = $%.2f）",
			notional, remainingDaily, int(dailyBuyRatio*100), maxDaily)
	}
	room := SymbolBuyRoom(netAssets, maxSymbolPct, existingMV)
	if notional > room+1e-6 {
		return fmt.Sprintf("超过单标的仓位上限（净资产 %d%%）", int(ClampMaxSymbolPositionPct(maxSymbolPct)*100))
	}
	gross := RemainingGrossRoom(netAssets, totalMV, MaxGrossExposurePct)
	if notional > gross+1e-6 {
		return fmt.Sprintf("总持仓已接近或超过净资产（持仓 $%.0f / 净资产 $%.0f），停止买入", totalMV, netAssets)
	}
	if notional > availableCash+1e-6 {
		return fmt.Sprintf("可用现金不足（需要 $%.2f，可用 $%.2f）", notional, availableCash)
	}
	return ""
}

func SellBlockedReason(quantity, availableQty float64) string {
	if quantity <= 0 {
		return "卖出数量必须大于 0"
	}
	if availableQty <= 0 {
		return "无可用持仓，无法卖出"
	}
	if quantity > availableQty+1e-6 {
		return fmt.Sprintf("卖出数量 %g 超过可用持仓 %g", quantity, availableQty)
	}
	return ""
}

func PositionQuantity(pos *Position) float64 {
	if pos == nil {
		return 0
	}
	for _, qty := range []float64{pos.AvailableQuantity, pos.Quantity} {
		if qty > 0 {
			return qty
		}
	}
	return 0
}

func ExistingPositionMarketValue(pos *Position, lastPrice float64, fx *FxRates) float64 {
	if pos == nil {
		return 0
	}
	currency := strings.ToUpper(strings.TrimSpace(pos.Currency))
	localMV := pos.MarketValue
	if localMV <= 0 {
		qty := PositionQuantity(pos)
		if qty <= 0 {
			return 0
		}
		if lastPrice > 0 {
			localMV = qty * lastPrice
		} else if pos.CostPrice > 0 {
			localMV = qty * pos.CostPrice
		} else if pos.LastPrice > 0 {
			localMV = qty * pos.LastPrice
		}
	}
	if localMV <= 0 {
		return 0
	}
	if fx == nil {
		return localMV
	}
	if currency == "" {
		_, mkt := ParseSymbolMarket(pos.Symbol, "US")
		currency = fx.OrderCurrency(mkt)
	}
	return math.Round(fx.ToUSD(localMV, currency)*100) / 100
}

func TotalPositionMarketValue(positions []Position, fx *FxRates, lastPrices map[string]float64) float64 {
	var total float64
	for i := range positions {
		last := 0.0
		if lastPrices != nil {
			last = lastPrices[positions[i].Symbol]
		}
		total += ExistingPositionMarketValue(&positions[i], last, fx)
	}
	return math.Round(total*100) / 100
}

func ShouldSkipHeldBuy(pos *Position) bool { return PositionQuantity(pos) > 0 }

func ShouldSkipDuplicateBuy(symbol string, todayBought map[string]struct{}) bool {
	code, _ := ParseSymbolMarket(symbol, "US")
	if code == "" || todayBought == nil {
		return false
	}
	_, ok := todayBought[code]
	return ok
}

const MinTargetAmountUSD = 50
const DailyBuyPositionRatio = 0.20

func CheckDailyLimits(todayOrders, maxOrders int, todayNotional, maxNotional float64) string {
	if todayOrders >= maxOrders {
		return fmt.Sprintf("已达日内最大订单数限制 (%d/%d)", todayOrders, maxOrders)
	}
	if todayNotional >= maxNotional {
		return fmt.Sprintf("已达日内名义本金上限 ($%.2f/$%.2f)", todayNotional, maxNotional)
	}
	return ""
}

func SlippageExceeded(signalPrice, realtimePrice, tolerance float64) bool {
	if realtimePrice <= 0 {
		return true
	}
	if signalPrice <= 0 {
		return false
	}
	return math.Abs(realtimePrice-signalPrice)/signalPrice > tolerance
}

func ResolveSubmitPermission(execute, configured, autoTradeEnabled bool) (allowed bool, reason string) {
	if !execute {
		return false, "仅扫描不下单"
	}
	if !configured {
		return false, "长桥凭据未配置，已跳过委托"
	}
	if !autoTradeEnabled {
		return false, "当前账户未开启自动交易，已跳过委托"
	}
	return true, ""
}
