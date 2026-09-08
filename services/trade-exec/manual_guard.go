package tradeexec

import "context"

// ManualEvalInput is the portal manual-order guard context.
type ManualEvalInput struct {
	Symbol   string
	Side     string
	Quantity float64
	Price    float64
	Market   string
	Settings UserSettings
	Fx       FxRates
	Halted   HaltState
}

// ManualEvalResult matches Python evaluate_manual_order return shape.
type ManualEvalResult struct {
	OK      bool    `json:"ok"`
	Blocked bool    `json:"blocked"`
	Message string  `json:"message"`
	Reason  string  `json:"reason,omitempty"`
	Notional float64 `json:"notional,omitempty"`
}

func RejectManual(message string) ManualEvalResult {
	return ManualEvalResult{OK: false, Blocked: true, Message: message, Reason: message}
}

// EvaluateManualOrder is the pure guard path before broker submit.
func EvaluateManualOrder(
	account Account,
	positions []Position,
	todayOrders []Order,
	in ManualEvalInput,
	lastPrice float64,
) ManualEvalResult {
	if block := HaltBlockReason(in.Halted); block != "" {
		return RejectManual(block)
	}
	if !account.Configured {
		return RejectManual("长桥凭据未配置")
	}
	code, mkt := ParseSymbolMarket(in.Symbol, in.Market)
	if in.Market != "" {
		mkt = in.Market
	}
	if NormalizeSide(in.Side) == "sell" {
		pos := MatchPosition(positions, code, mkt)
		avail := PositionQuantity(pos)
		if reason := SellBlockedReason(in.Quantity, avail); reason != "" {
			return RejectManual(reason)
		}
		return ManualEvalResult{OK: true, Blocked: false, Message: ""}
	}
	px := lastPrice
	if px <= 0 {
		px = in.Price
	}
	_, todayNotional := TodayBuyNotionalFromOrders(todayOrders)
	netAssets := PickNetAssets(account, in.Fx)
	availableCash := PickAvailableCash(account, in.Fx)
	lastPrices := map[string]float64{}
	if px > 0 {
		lastPrices[code] = px
	}
	totalMV := TotalPositionMarketValue(positions, &in.Fx, lastPrices)
	pos := MatchPosition(positions, code, mkt)
	existingMV := ExistingPositionMarketValue(pos, px, &in.Fx)
	notional := OrderNotional(in.Quantity, px)
	if reason := BuyBlockedReason(
		notional, netAssets, availableCash, totalMV, existingMV, todayNotional,
		in.Settings.DailyBuyRatio, in.Settings.MaxSymbolPositionPct,
	); reason != "" {
		return RejectManual(reason)
	}
	return ManualEvalResult{OK: true, Blocked: false, Message: "", Notional: notional}
}

// BrokerSnapshot loads account/positions/orders for manual guard (testable).
type BrokerSnapshot struct {
	Account     Account
	Positions   []Position
	TodayOrders []Order
}

func LoadBrokerSnapshot(ctx context.Context, broker Broker, creds Creds) (BrokerSnapshot, error) {
	acc, err := broker.AccountBalance(ctx, creds)
	if err != nil {
		return BrokerSnapshot{}, err
	}
	pos, err := broker.Positions(ctx, creds)
	if err != nil {
		return BrokerSnapshot{}, err
	}
	orders, err := broker.TodayOrders(ctx, creds)
	if err != nil {
		return BrokerSnapshot{}, err
	}
	return BrokerSnapshot{Account: acc, Positions: pos, TodayOrders: orders}, nil
}
