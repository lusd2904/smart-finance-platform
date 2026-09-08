package jobs

import (
	"context"
	"fmt"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
	"github.com/redis/go-redis/v9"
)

const StopLossPct = -8.0

type KlineCloseFn func(ctx context.Context, market string, symbols []string) (map[string]float64, error)

func RunPositionMonitor(ctx context.Context, repo *Repo, broker tradeexec.Broker, rdb *redis.Client, keys EncKeys, kline KlineCloseFn) (map[string]interface{}, error) {
	userIDs, err := repo.ListConfiguredUserIDs(ctx)
	if err != nil {
		return nil, err
	}
	asOf := tradeexec.BeijingNow()
	if len(userIDs) == 0 {
		payload := map[string]interface{}{
			"configured": false,
			"message":    "没有已配置长桥的账户，跳过持仓监控",
			"alerts":     []interface{}{},
			"asOf":       asOf,
		}
		_ = putScheduled(ctx, rdb, "positions", payload)
		return payload, nil
	}

	var alerts []map[string]interface{}
	sold := 0
	positionCount := 0
	for _, uid := range userIDs {
		settings := repo.LoadSettings(ctx, uid)
		creds, err := repo.LoadCreds(ctx, uid, keys.CredentialKey, keys.JWTSecret, keys.AppEnv)
		if err != nil || !creds.Configured() {
			continue
		}
		positions, err := broker.Positions(ctx, creds)
		if err != nil {
			continue
		}
		positionCount += len(positions)
		for _, pos := range positions {
			raw := pos.Symbol
			if raw == "" {
				continue
			}
			symbol, market := tradeexec.ParseSymbolMarket(raw, "US")
			qty := tradeexec.PositionQuantity(&pos)
			cost := pos.CostPrice
			last := pos.LastPrice
			if last <= 0 {
				quotes, qerr := broker.RealtimeQuotes(ctx, creds, []string{symbol}, market)
				if qerr == nil {
					last = tradeexec.ExtractLastPrice(quotes, tradeexec.ToLongbridgeSymbol(symbol, market))
				}
			}
			if last <= 0 && kline != nil {
				closes, _ := kline(ctx, market, []string{symbol})
				last = closes[symbol]
			}
			if cost <= 0 || last <= 0 {
				continue
			}
			pnlPct := (last - cost) / cost * 100
			if pnlPct > StopLossPct {
				continue
			}
			alert := map[string]interface{}{
				"userId":    uid,
				"symbol":    symbol,
				"market":    market,
				"quantity":  qty,
				"costPrice": cost,
				"lastPrice": last,
				"pnlPct":    round4(pnlPct),
				"level":     "danger",
				"title":     fmt.Sprintf("持仓止损 · %s", symbol),
				"content":   fmt.Sprintf("用户%d %s 现价 %v 相对成本 %v 浮亏 %.4f%%，触发 %.0f%% 止损线", uid, symbol, last, cost, pnlPct, StopLossPct),
			}
			var orderOK bool
			if settings.AutoTradeEnabled && qty > 0 {
				res := broker.SubmitOrder(ctx, creds, tradeexec.SubmitReq{
					Symbol: symbol, Side: "SELL", Quantity: float64(int(qty)), OrderType: "MO", Market: market,
				})
				orderOK = res.OK
				status := "rejected"
				orderID := ""
				errText := res.Message
				if orderOK {
					status = "submitted"
					orderID = res.OrderID
					errText = ""
					sold++
					alert["content"] = alert["content"].(string) + "；已按市价卖出"
				} else {
					if errText == "" {
						errText = "止损下单失败"
					}
					alert["content"] = alert["content"].(string) + "；下单失败 " + res.Message
				}
				_ = repo.InsertDecision(ctx, DecisionRow{
					CycleID:  fmt.Sprintf("stoploss_%s", time.Now().Format("20060102_150405")),
					UserID:   uid,
					Symbol:   symbol,
					Market:   market,
					Side:     "SELL",
					Quantity: int(qty),
					Price:    last,
					Status:   status,
					Reason:   alert["content"].(string),
					Source:   "stop_loss",
					OrderID:  orderID,
					Error:    errText,
				})
			} else if !settings.AutoTradeEnabled {
				alert["content"] = alert["content"].(string) + "；本账户自动交易未开，仅记录"
			}
			alerts = append(alerts, alert)
			dup, _ := repo.HasPendingRisk(ctx, uid, symbol)
			if !dup {
				review := "pending_review"
				handled := "0"
				if orderOK {
					review = "handled"
					handled = "1"
				}
				_ = repo.InsertRiskEvent(ctx, uid, "danger", alert["title"].(string), alert["content"].(string), symbol, review, handled)
			}
		}
	}
	payload := map[string]interface{}{
		"configured": true,
		"count":      positionCount,
		"alertCount": len(alerts),
		"soldCount":  sold,
		"alerts":     alerts,
		"asOf":       asOf,
	}
	_ = repo.InsertReadmodel(ctx, "positions", payload)
	_ = putScheduled(ctx, rdb, "positions", payload)
	return map[string]interface{}{
		"configured": true,
		"count":      positionCount,
		"alertCount": len(alerts),
		"soldCount":  sold,
	}, nil
}

func putScheduled(ctx context.Context, rdb *redis.Client, kind string, payload interface{}) error {
	if rdb == nil {
		return nil
	}
	raw, err := jsonBytes(payload)
	if err != nil {
		return err
	}
	return rdb.Set(ctx, "readmodel:scheduled:"+kind, raw, 15*time.Minute).Err()
}
