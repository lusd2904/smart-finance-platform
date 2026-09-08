package store

import (
	"context"
	"database/sql"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/calendar"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factor"
)

func (s *Service) RunDailyListScan(ctx context.Context, payload map[string]any) (map[string]any, error) {
	override := payloadString(payload, "profile")
	userID := payloadInt(payload, "userId")
	if userID > 0 {
		profile := s.resolveProfile(ctx, userID, override)
		return s.scanDailyListUser(ctx, userID, profile)
	}
	now := time.Now()
	if !calendar.IsCNTradingDay(calendar.TodayCN(now)) {
		return map[string]any{"skipped": true, "reason": "non_trading_day", "message": "非交易日跳过"}, nil
	}
	users, err := s.watchlistUsers(ctx)
	if err != nil {
		return nil, err
	}
	results := []map[string]any{}
	for _, uid := range users {
		profile := s.resolveProfile(ctx, uid, override)
		one, err := s.scanDailyListUser(ctx, uid, profile)
		if err != nil {
			results = append(results, map[string]any{"userId": uid, "error": err.Error()})
			continue
		}
		results = append(results, one)
	}
	return map[string]any{"skipped": false, "userCount": len(users), "results": results}, nil
}

func (s *Service) scanDailyListUser(ctx context.Context, userID int, profile string) (map[string]any, error) {
	scanDate := calendar.TodayCN(time.Now())
	tradeDate := calendar.NextCNTradingDay(scanDate)
	if !calendar.IsCNTradingDay(scanDate) {
		return s.upsertDailyList(ctx, userID, scanDate, tradeDate, profile, "skipped", "非交易日，不生成可交易清单", nil, nil)
	}

	watch, err := s.enabledWatchlist(ctx, userID)
	if err != nil {
		return nil, err
	}
	if len(watch) > maxScanSyms {
		watch = watch[:maxScanSyms]
	}
	if len(watch) == 0 {
		return s.upsertDailyList(ctx, userID, scanDate, tradeDate, profile, "empty", "自选为空，未生成清单", nil, nil)
	}

	cfg := s.loadProfileConfig(ctx, profile, userID)
	pairs := make([]symbolMarket, 0, len(watch))
	nameMap := map[string]string{}
	for _, w := range watch {
		pairs = append(pairs, symbolMarket{w.Symbol, w.Market})
		nameMap[w.Symbol+"|"+w.Market] = w.Name
	}
	klines, _ := s.prefetchKlines(ctx, pairs, "-1y", 320)
	buys := []factor.Signal{}
	for _, w := range watch {
		sig := factor.EvaluateSymbol(w.Symbol, w.Market, profile, toFactorBars(klines[w.Symbol+"|"+w.Market]), cfg)
		if strings.EqualFold(sig.Signal, "BUY") {
			buys = append(buys, sig)
		}
	}
	if len(buys) == 0 {
		return s.upsertDailyList(ctx, userID, scanDate, tradeDate, profile, "empty", "策略无买入标的，静默不生成可交易清单", nil, nameMap)
	}
	return s.upsertDailyList(ctx, userID, scanDate, tradeDate, profile, "open",
		"已生成 "+itoa(len(buys))+" 只次日标的", buys, nameMap)
}

func (s *Service) upsertDailyList(ctx context.Context, userID int, scanDate, tradeDate time.Time, profile, status, message string, buys []factor.Signal, nameMap map[string]string) (map[string]any, error) {
	scanS := calendar.FormatDate(scanDate)
	tradeS := calendar.FormatDate(tradeDate)
	var listID int64
	err := s.db.QueryRowContext(ctx, `
SELECT list_id FROM quant_daily_list WHERE user_id = ? AND trade_date = ?`, userID, tradeS).Scan(&listID)
	if err == sql.ErrNoRows {
		res, err := s.db.ExecContext(ctx, `
INSERT INTO quant_daily_list
(user_id, scan_date, trade_date, profile, status, auto_enabled, item_count, message, create_time, update_time)
VALUES (?, ?, ?, ?, ?, '0', ?, ?, NOW(), NOW())`,
			userID, scanS, tradeS, profile, status, len(buys), message)
		if err != nil {
			return nil, err
		}
		listID, _ = res.LastInsertId()
	} else if err != nil {
		return nil, err
	} else {
		if _, err := s.db.ExecContext(ctx, `
UPDATE quant_daily_list
SET scan_date=?, profile=?, status=?, item_count=?, message=?, update_time=NOW()
WHERE list_id=?`, scanS, profile, status, len(buys), message, listID); err != nil {
			return nil, err
		}
	}
	if _, err := s.db.ExecContext(ctx, `DELETE FROM quant_daily_list_item WHERE list_id=?`, listID); err != nil {
		return nil, err
	}
	items := []map[string]any{}
	for _, sig := range buys {
		name := ""
		if nameMap != nil {
			name = nameMap[sig.Symbol+"|"+sig.Market]
		}
		res, err := s.db.ExecContext(ctx, `
INSERT INTO quant_daily_list_item
(list_id, user_id, trade_date, symbol, market, name, signal, score, confidence, reason,
 selected, auto_trade, status, side, create_time, update_time)
VALUES (?, ?, ?, ?, ?, ?, 'BUY', ?, ?, ?, '0', '0', 'listed', 'BUY', NOW(), NOW())`,
			listID, userID, tradeS, sig.Symbol, sig.Market, name, sig.Score, sig.Confidence, truncate(sig.Reason, 500))
		if err != nil {
			return nil, err
		}
		itemID, _ := res.LastInsertId()
		items = append(items, map[string]any{
			"itemId": itemID, "listId": listID, "symbol": sig.Symbol, "market": sig.Market,
			"name": name, "signal": "BUY", "score": sig.Score, "confidence": sig.Confidence,
			"reason": sig.Reason, "selected": false, "autoTrade": false, "status": "listed", "side": "BUY",
		})
	}
	return map[string]any{
		"listId": listID, "userId": userID, "scanDate": scanS, "tradeDate": tradeS,
		"profile": profile, "status": status, "autoEnabled": false,
		"itemCount": len(items), "message": message, "items": items,
	}, nil
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	neg := n < 0
	if neg {
		n = -n
	}
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	if neg {
		s = "-" + s
	}
	return s
}
