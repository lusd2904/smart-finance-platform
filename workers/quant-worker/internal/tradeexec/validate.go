package tradeexec

import (
	"fmt"
	"math"
	"strings"
)

var allowedOrderTypes = map[string]struct{}{"LO": {}, "MO": {}, "ELO": {}, "AO": {}}

// ValidateOrderInput mirrors Python TradeClientMixin._validate_order_input.
func ValidateOrderInput(symbol, side string, quantity float64, orderType string, price float64, hasPrice bool) string {
	if strings.TrimSpace(symbol) == "" {
		return "标的代码不能为空"
	}
	norm := NormalizeSide(side)
	if norm != "buy" && norm != "sell" {
		return fmt.Sprintf("无效交易方向: %q（仅支持 buy/sell）", side)
	}
	if math.IsNaN(quantity) || math.IsInf(quantity, 0) || quantity <= 0 {
		return "下单数量必须为大于0的有限数值"
	}
	ot := strings.ToUpper(strings.TrimSpace(orderType))
	if ot == "" {
		ot = "LO"
	}
	if _, ok := allowedOrderTypes[ot]; !ok {
		return fmt.Sprintf("不支持的订单类型: %q（仅支持 LO/MO/ELO/AO）", orderType)
	}
	if ot == "MO" {
		return ""
	}
	if !hasPrice || math.IsNaN(price) || math.IsInf(price, 0) || price <= 0 {
		return fmt.Sprintf("%s 订单必须提供大于0的有效价格", ot)
	}
	return ""
}

func NormalizeOrderType(orderType string) string {
	ot := strings.ToUpper(strings.TrimSpace(orderType))
	if ot == "" {
		return "LO"
	}
	return ot
}

func ExtractOrderID(res SubmitResult) string {
	if !res.OK || res.OrderID == "" {
		return ""
	}
	return res.OrderID
}

func ExtractLastPrice(quotes []Quote, symbol string) float64 {
	if symbol != "" {
		target := strings.ToUpper(strings.TrimSpace(symbol))
		lb := strings.ToUpper(ToLongbridgeSymbol(target, "US"))
		for _, q := range quotes {
			qSym := strings.ToUpper(q.Symbol)
			if qSym == target || qSym == lb {
				if q.LastDone > 0 {
					return q.LastDone
				}
				return q.Last
			}
		}
	}
	if len(quotes) > 0 {
		if quotes[0].LastDone > 0 {
			return quotes[0].LastDone
		}
		return quotes[0].Last
	}
	return 0
}

func QuoteLastForSymbol(quotes []Quote, symbol, market string, remainingCount int) float64 {
	lb := ToLongbridgeSymbol(symbol, market)
	keys := SymbolMatchKeys(symbol)
	for k := range SymbolMatchKeys(lb) {
		keys[k] = struct{}{}
	}
	var matched []Quote
	for _, row := range quotes {
		if keysIntersect(keys, SymbolMatchKeys(row.Symbol)) {
			matched = append(matched, row)
		}
	}
	if len(matched) == 0 && remainingCount == 1 {
		matched = quotes
	}
	return ExtractLastPrice(matched, lb)
}
