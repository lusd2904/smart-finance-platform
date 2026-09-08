package tradeexec

import "testing"

func TestEvaluateManualOrderBuyBlockedByHalt(t *testing.T) {
	acc := Account{Configured: true, Balances: []Balance{{Currency: "USD", NetAssets: 10000, AvailableCash: 5000}}}
	eval := EvaluateManualOrder(acc, nil, nil, ManualEvalInput{
		Symbol: "AAPL", Side: "buy", Quantity: 1, Price: 100, Market: "US",
		Settings: UserSettings{DailyBuyRatio: 0.2, MaxSymbolPositionPct: 0.1},
		Fx:       NewFxRates(),
		Halted:   HaltState{Halted: true, Reason: "test"},
	}, 100)
	if eval.OK || !eval.Blocked {
		t.Fatalf("expected halt block, got %+v", eval)
	}
}

func TestEvaluateManualOrderSellExceedsPosition(t *testing.T) {
	pos := []Position{{Symbol: "AAPL.US", Quantity: 5, AvailableQuantity: 5}}
	acc := Account{Configured: true}
	eval := EvaluateManualOrder(acc, pos, nil, ManualEvalInput{
		Symbol: "AAPL", Side: "sell", Quantity: 10, Market: "US",
		Settings: UserSettings{}, Fx: NewFxRates(),
	}, 0)
	if eval.OK {
		t.Fatalf("expected sell block, got %+v", eval)
	}
}
