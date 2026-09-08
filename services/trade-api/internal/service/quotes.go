package service

import (
	"context"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/influx"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/kline"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/repo"
	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

type Quotes struct {
	Broker *repo.Repo
	Influx *influx.Client
	Sdk    tradeexec.Broker
}

func (q *Quotes) creds(ctx context.Context, userID int) (tradeexec.Creds, error) {
	return q.Broker.LoadCreds(ctx, userID)
}

func (q *Quotes) QuoteDepth(ctx context.Context, userID int, symbol, market string) map[string]interface{} {
	creds, _ := q.creds(ctx, userID)
	if sdk, ok := q.Sdk.(*tradeexec.SDKBroker); ok {
		return sdk.GetDepth(ctx, creds, symbol, market)
	}
	return sdkBroker(q.Sdk).GetDepth(ctx, creds, symbol, market)
}

func (q *Quotes) QuoteTrades(ctx context.Context, userID int, symbol, market string, count int) map[string]interface{} {
	creds, _ := q.creds(ctx, userID)
	return sdkBroker(q.Sdk).GetTrades(ctx, creds, symbol, market, count)
}

func (q *Quotes) QuoteSnapshot(ctx context.Context, userID int, symbol, market string) map[string]interface{} {
	creds, _ := q.creds(ctx, userID)
	return sdkBroker(q.Sdk).GetQuoteSnapshot(ctx, creds, symbol, market)
}

func (q *Quotes) QuoteKline(ctx context.Context, userID int, symbol, market, period string, limit int) (map[string]interface{}, error) {
	code, mkt := tradeexec.ParseSymbolMarket(symbol, market)
	periodKey := kline.NormalizePeriod(period)
	if limit <= 0 {
		limit = 200
	}
	if limit < 20 {
		limit = 20
	}
	if limit > 500 {
		limit = 500
	}
	if mkt == "US" && kline.IsMinutePeriod(periodKey) {
		if limit < 500 {
			limit = 500
		}
	}
	creds, _ := q.creds(ctx, userID)
	configured := creds.Configured()
	klines := []map[string]interface{}{}
	source := "influx"
	message := ""
	fallback := ""

	if q.Influx != nil {
		lim := limit
		bars, err := q.Influx.GetKlineSeries(ctx, mkt, code, periodKey, "", "now()", &lim)
		if err == nil && len(bars) > 0 {
			klines = kline.BarsToMaps(bars)
		}
	}
	if len(klines) == 0 && configured && kline.IsMinutePeriod(periodKey) && (mkt == "US" || mkt == "HK") && !strings.HasPrefix(code, "^") {
		lbPeriod := periodKey
		if periodKey == "intraday" {
			data := sdkBroker(q.Sdk).GetIntraday(ctx, creds, code, mkt)
			if items, ok := data["klines"].([]map[string]interface{}); ok && len(items) > 0 {
				klines = items
				source = "longbridge"
			} else if arr, ok := data["klines"].([]interface{}); ok {
				for _, it := range arr {
					if row, ok := it.(map[string]interface{}); ok {
						klines = append(klines, row)
					}
				}
				if len(klines) > 0 {
					source = "longbridge"
				}
			}
		} else {
			data := sdkBroker(q.Sdk).GetCandlesticks(ctx, creds, code, mkt, lbPeriod, limit)
			if items, ok := data["klines"].([]interface{}); ok {
				for _, it := range items {
					if row, ok := it.(map[string]interface{}); ok {
						klines = append(klines, row)
					}
				}
				if len(klines) > 0 {
					source = "longbridge"
					fallback = "influx_empty"
				}
			}
		}
	}
	if len(klines) == 0 && message == "" {
		message = "暂无K线"
	}
	if len(klines) > limit {
		klines = klines[len(klines)-limit:]
	}
	quote := quoteFromKlines(klines)
	priceSource := source
	if source == "influx" {
		priceSource = "history"
	}
	out := map[string]interface{}{
		"symbol": code, "market": mkt, "period": periodKey, "source": source,
		"priceSource": priceSource, "configured": configured, "message": message,
		"session": sessionTag(mkt), "klines": klines, "quote": quote,
	}
	if fallback != "" {
		out["fallback"] = fallback
	}
	if quote != nil {
		out["quote"] = map[string]interface{}{}
		for k, v := range quote {
			out["quote"].(map[string]interface{})[k] = v
		}
		out["quote"].(map[string]interface{})["source"] = priceSource
	}
	return out, nil
}

func sdkBroker(b tradeexec.Broker) *tradeexec.SDKBroker {
	if sdk, ok := b.(*tradeexec.SDKBroker); ok {
		return sdk
	}
	return tradeexec.NewSDKBroker()
}

func quoteFromKlines(klines []map[string]interface{}) map[string]interface{} {
	if len(klines) == 0 {
		return map[string]interface{}{}
	}
	last := klines[len(klines)-1]
	prev := map[string]interface{}{}
	if len(klines) > 1 {
		prev = klines[len(klines)-2]
	}
	close := num(last["close"])
	prevClose := num(prev["close"])
	change := 0.0
	changeRate := 0.0
	if prevClose > 0 && close > 0 {
		change = close - prevClose
		changeRate = change / prevClose * 100
	}
	return map[string]interface{}{
		"last": close, "open": num(last["open"]), "high": num(last["high"]),
		"low": num(last["low"]), "volume": num(last["volume"]),
		"prevClose": prevClose, "change": change, "changeRate": changeRate,
	}
}

func sessionTag(market string) string {
	if strings.ToUpper(market) == "US" {
		return "us"
	}
	if strings.ToUpper(market) == "HK" {
		return "hk"
	}
	return "cn"
}

func num(v interface{}) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case int:
		return float64(x)
	case int64:
		return float64(x)
	default:
		return 0
	}
}
