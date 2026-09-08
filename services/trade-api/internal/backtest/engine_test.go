package backtest

import "testing"

func TestSimulateLongOnly(t *testing.T) {
	klines := []Kline{
		{Date: "2024-01-01", Close: 100},
		{Date: "2024-01-02", Close: 102},
		{Date: "2024-01-03", Close: 101},
		{Date: "2024-01-04", Close: 105},
	}
	signals := []string{"HOLD", "BUY", "HOLD", "SELL"}
	res := SimulateLongOnly(klines, signals, 10000, DefaultFee, DefaultSlip)
	if !res.OK {
		t.Fatalf("expected ok result")
	}
	if res.Trades < 2 {
		t.Fatalf("expected at least 2 trades, got %d", res.Trades)
	}
}

func TestFactorSignals(t *testing.T) {
	klines := make([]Kline, 40)
	for i := range klines {
		klines[i] = Kline{Date: "2024-01-01", Close: 100 + float64(i)}
	}
	signals := FactorSignals(klines, "balanced", nil)
	if len(signals) != len(klines) {
		t.Fatalf("signal length mismatch")
	}
}
