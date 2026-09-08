package jobs

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/delegate"
)

type PythonStrategy struct {
	Client *delegate.PythonClient
}

func (p *PythonStrategy) Evaluate(ctx context.Context, profile string, userID int, targets []Target) ([]StrategySignal, error) {
	if p == nil || p.Client == nil {
		return nil, fmt.Errorf("strategy evaluate client is not configured")
	}
	symbols := make([]map[string]string, 0, len(targets))
	for _, t := range targets {
		symbols = append(symbols, map[string]string{"symbol": t.Symbol, "market": t.Market})
	}
	out, err := p.Client.Run(ctx, "strategy_evaluate", map[string]interface{}{
		"profile": profile,
		"userId":  userID,
		"symbols": symbols,
	})
	if err != nil {
		return nil, err
	}
	raw := out["result"]
	if raw == nil {
		raw = out["signals"]
	}
	result, _ := raw.(map[string]interface{})
	var list []interface{}
	if result != nil {
		list, _ = result["signals"].([]interface{})
	}
	if list == nil {
		if direct, ok := out["signals"].([]interface{}); ok {
			list = direct
		}
	}
	signals := make([]StrategySignal, 0, len(list))
	for _, item := range list {
		m, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		sig := StrategySignal{
			Symbol:     strings.TrimSpace(fmt.Sprint(m["symbol"])),
			Market:     strings.ToUpper(strings.TrimSpace(fmt.Sprint(m["market"]))),
			Signal:     strings.ToUpper(strings.TrimSpace(fmt.Sprint(m["signal"]))),
			Score:      asFloat(m["score"]),
			Confidence: int(asFloat(m["confidence"])),
			Reason:     fmt.Sprint(m["reason"]),
			Price:      asFloat(m["price"]),
		}
		if sig.Market == "" || sig.Market == "<NIL>" {
			sig.Market = "US"
		}
		if sig.Reason == "<nil>" {
			sig.Reason = ""
		}
		signals = append(signals, sig)
	}
	return signals, nil
}

func asFloat(v interface{}) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case float32:
		return float64(x)
	case int:
		return float64(x)
	case int64:
		return float64(x)
	case json.Number:
		f, _ := x.Float64()
		return f
	default:
		return 0
	}
}
