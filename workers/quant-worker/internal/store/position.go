package store

import (
	"context"
	"database/sql"
	"fmt"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/crypto"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/longbridge"
)

// RunPositionMonitor is read-only: alerts + plat_risk_event.
// Order submit (soldCount) stays with P1 Longbridge trade execution.
func (s *Service) RunPositionMonitor(ctx context.Context) (map[string]any, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT user_id, COALESCE(app_key,''), COALESCE(app_secret,''), COALESCE(access_token,''), COALESCE(region,'cn')
FROM quant_longbridge_config
WHERE app_key IS NOT NULL AND app_key <> '' AND access_token IS NOT NULL AND access_token <> ''`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	type acct struct {
		userID int
		creds  longbridge.Creds
	}
	accounts := []acct{}
	for rows.Next() {
		var uid int
		var key, secret, token, region string
		if err := rows.Scan(&uid, &key, &secret, &token, &region); err != nil {
			return nil, err
		}
		accounts = append(accounts, acct{userID: uid, creds: longbridge.Creds{
			AppKey:      strings.TrimSpace(key),
			AppSecret:   crypto.DecryptCredential(secret, s.cfg.CredentialKey, s.cfg.JWTSecret),
			AccessToken: crypto.DecryptCredential(token, s.cfg.CredentialKey, s.cfg.JWTSecret),
			Region:      region,
		}})
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(accounts) == 0 {
		payload := map[string]any{
			"configured": false,
			"message":    "没有已配置长桥的账户，跳过持仓监控",
			"alerts":     []any{},
			"asOf":       beijingNow(),
			"orderHandoff": "p1",
		}
		_ = s.putScheduled(ctx, "positions", payload, boardTTL)
		return payload, nil
	}

	envFallback := longbridge.LoadCredsFromEnv()
	alerts := []map[string]any{}
	positionCount := 0
	for _, acct := range accounts {
		creds := acct.creds
		if !creds.Configured() && envFallback.Configured() {
			creds = envFallback
		}
		if !creds.Configured() {
			continue
		}
		client := longbridge.NewClient(creds)
		positions, err := client.GetPositions(ctx)
		if err != nil || positions == nil {
			continue
		}
		positionCount += len(positions)
		for _, pos := range positions {
			raw := strings.TrimSpace(pos.Symbol)
			if raw == "" {
				continue
			}
			symbol, market := longbridge.ParseSymbolMarket(raw, pos.Market)
			qty := pos.AvailableQuantity
			if qty == 0 {
				qty = pos.Quantity
			}
			cost := pos.CostPrice
			last := pos.LastPrice
			if last == 0 {
				bars, qerr := s.reader.QueryLatestKlines(ctx, market, []string{symbol}, 1, "-30d")
				if qerr == nil {
					if bb := bars[symbol]; len(bb) > 0 {
						last = bb[len(bb)-1].Close
					}
				}
			}
			if cost == 0 || last == 0 {
				continue
			}
			pnl := (last - cost) / cost * 100
			if pnl > stopLossPct {
				continue
			}
			alert := map[string]any{
				"userId": acct.userID, "symbol": symbol, "market": market,
				"quantity": qty, "costPrice": cost, "lastPrice": last,
				"pnlPct": storeRound4(pnl), "level": "danger",
				"title":   fmt.Sprintf("持仓止损 · %s", symbol),
				"content": fmt.Sprintf("用户%d %s 现价 %v 相对成本 %v 浮亏 %.4f%%，触发 %v%% 止损线；自动卖出交由 P1 交易执行", acct.userID, symbol, last, cost, pnl, stopLossPct),
			}
			alerts = append(alerts, alert)
			if !s.hasOpenRisk(ctx, acct.userID, symbol) {
				_, _ = s.db.ExecContext(ctx, `
INSERT INTO plat_risk_event
(user_id, rule_id, event_level, title, content, symbol, handled, review_status, create_time)
VALUES (?, NULL, 'danger', ?, ?, ?, '0', 'pending_review', NOW())`,
					acct.userID, alert["title"], alert["content"], symbol)
			}
		}
	}
	payload := map[string]any{
		"configured":   true,
		"count":        positionCount,
		"alertCount":   len(alerts),
		"soldCount":    0,
		"alerts":       alerts,
		"asOf":         beijingNow(),
		"orderHandoff": "p1",
		"message":      "只读监控：止损告警已落库；市价卖出由 P1 Longbridge 执行链路处理",
	}
	if err := s.addReadmodel(ctx, "positions", mustJSON(payload)); err != nil {
		return nil, err
	}
	_ = s.putScheduled(ctx, "positions", payload, boardTTL)
	return map[string]any{
		"configured": true, "count": positionCount, "alertCount": len(alerts),
		"soldCount": 0, "orderHandoff": "p1",
	}, nil
}

func (s *Service) hasOpenRisk(ctx context.Context, userID int, symbol string) bool {
	var n int
	err := s.db.QueryRowContext(ctx, `
SELECT COUNT(*) FROM plat_risk_event
WHERE user_id = ? AND symbol = ?
  AND review_status IN ('pending_review','need_review','overdue')
LIMIT 80`, userID, symbol).Scan(&n)
	if err == sql.ErrNoRows {
		return false
	}
	return err == nil && n > 0
}

func storeRound4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}
