package tradeexec

// FlattenAccount mirrors Python LongbridgeService.flatten_account for portal payloads.
func FlattenAccount(account Account) map[string]interface{} {
	balances := RawBalanceRows(account)
	first := map[string]interface{}{}
	if len(balances) > 0 {
		first = balances[0]
	}
	if !account.Configured {
		msg := account.Message
		if msg == "" {
			msg = "长桥凭据未配置"
		}
		return map[string]interface{}{
			"configured":    false,
			"message":       msg,
			"currency":      nil,
			"totalCash":     nil,
			"availableCash": nil,
			"netAssets":     nil,
			"balances":      []map[string]interface{}{},
		}
	}
	return map[string]interface{}{
		"configured":    true,
		"message":       account.Message,
		"currency":      strOr(first["currency"], "USD"),
		"totalCash":     floatOr(first["totalCash"], 0),
		"availableCash": floatOr(first["availableCash"], floatOr(first["totalCash"], 0)),
		"netAssets":     floatOr(first["netAssets"], floatOr(first["totalCash"], 0)),
		"balances":      balances,
	}
}

func OrderToMap(o Order) map[string]interface{} {
	return map[string]interface{}{
		"orderId":          o.OrderID,
		"symbol":           o.Symbol,
		"stockName":        o.StockName,
		"side":             o.Side,
		"status":           o.Status,
		"statusLabel":      o.StatusLabel,
		"orderType":        o.OrderType,
		"quantity":         o.Quantity,
		"price":            o.Price,
		"executedQuantity": o.ExecutedQuantity,
		"executedPrice":    o.ExecutedPrice,
		"currency":         o.Currency,
		"submittedAt":      o.SubmittedAt,
		"updatedAt":        o.UpdatedAt,
		"open":             o.Open,
	}
}

func OrdersPayload(orders []Order) map[string]interface{} {
	items := make([]map[string]interface{}, 0, len(orders))
	for _, o := range orders {
		items = append(items, OrderToMap(o))
	}
	return map[string]interface{}{"orders": items}
}

func MergePositionQuotes(positions []Position, quotes []Quote) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(positions))
	for _, p := range positions {
		last := 0.0
		prev := 0.0
		for _, q := range quotes {
			if keysIntersect(SymbolMatchKeys(p.Symbol), SymbolMatchKeys(q.Symbol)) {
				last = q.LastDone
				if last == 0 {
					last = q.Last
				}
				prev = q.PrevClose
				break
			}
		}
		row := map[string]interface{}{
			"symbol":            p.Symbol,
			"symbolName":        p.SymbolName,
			"quantity":          p.Quantity,
			"availableQuantity": p.AvailableQuantity,
			"costPrice":         p.CostPrice,
			"currency":          p.Currency,
		}
		if last > 0 {
			row["last"] = last
		}
		if prev > 0 {
			row["prevClose"] = prev
		}
		if last > 0 && prev > 0 {
			row["changePct"] = round2((last-prev)/prev*100)
		}
		if last > 0 && p.CostPrice > 0 {
			row["pnlPct"] = round2((last-p.CostPrice)/p.CostPrice*100)
		}
		out = append(out, row)
	}
	return out
}

func floatOr(v interface{}, fallback float64) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case float32:
		return float64(x)
	case int:
		return float64(x)
	case int64:
		return float64(x)
	default:
		return fallback
	}
}

func strOr(v interface{}, fallback string) string {
	if s, ok := v.(string); ok && s != "" {
		return s
	}
	return fallback
}

func round2(v float64) float64 {
	return float64(int(v*100+0.5)) / 100
}
