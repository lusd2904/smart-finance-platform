package jobs

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
)

const maxWatchlistBatch = 30

var recSign = map[string]bool{"买入": true, "减仓": true, "卖出": true}

func (s *Service) RunWatchlistAnalyze(ctx context.Context, payload map[string]interface{}) (map[string]interface{}, error) {
	symbol := strings.ToUpper(strings.TrimSpace(stringFrom(payload["symbol"])))
	userID := intFrom(payload["userId"])
	if symbol != "" {
		marketName := strings.ToUpper(stringFrom(payload["market"]))
		if marketName == "" {
			marketName = "US"
		}
		result, err := s.analyzeWatchlistOne(ctx, symbol, marketName, userID, nil, "")
		if err != nil {
			return nil, err
		}
		return result, nil
	}
	if userID > 0 {
		targets, err := s.listEnabledWatchlist(ctx, userID, maxWatchlistBatch)
		if err != nil {
			return nil, err
		}
		if len(targets) == 0 {
			return map[string]interface{}{"ok": false, "message": "自选清单为空，请先添加关注标的"}, nil
		}
		return s.runWatchlistTargets(ctx, targets)
	}
	return s.runWatchlistHourly(ctx)
}

func (s *Service) runWatchlistHourly(ctx context.Context) (map[string]interface{}, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT DISTINCT user_id FROM market_watchlist WHERE enabled = '1' AND user_id IS NOT NULL`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	userCount := 0
	allItems := []map[string]interface{}{}
	allFailed := []map[string]interface{}{}
	for rows.Next() {
		var uid sql.NullInt64
		if err := rows.Scan(&uid); err != nil {
			return nil, err
		}
		if !uid.Valid || uid.Int64 <= 0 {
			continue
		}
		targets, err := s.listEnabledWatchlist(ctx, uid.Int64, maxWatchlistBatch)
		if err != nil {
			return nil, err
		}
		if len(targets) == 0 {
			continue
		}
		userCount++
		result, err := s.runWatchlistTargets(ctx, targets)
		if err != nil {
			return nil, err
		}
		if items, ok := result["items"].([]map[string]interface{}); ok {
			allItems = append(allItems, items...)
		}
		if failed, ok := result["failed"].([]map[string]interface{}); ok {
			allFailed = append(allFailed, failed...)
		}
	}
	return map[string]interface{}{
		"ok": true, "users": userCount, "count": len(allItems), "failedCount": len(allFailed),
		"aiAvailable": true, "items": allItems, "failed": allFailed,
		"message": fmt.Sprintf("完成 %d 只，失败 %d 只", len(allItems), len(allFailed)),
	}, nil
}

func (s *Service) runWatchlistTargets(ctx context.Context, targets []watchlistTarget) (map[string]interface{}, error) {
	items := []map[string]interface{}{}
	failed := []map[string]interface{}{}
	for _, target := range targets {
		result, err := s.analyzeWatchlistOne(ctx, target.Symbol, target.Market, target.UserID, target.ID, target.Name)
		if err != nil {
			failed = append(failed, map[string]interface{}{"symbol": target.Symbol, "market": target.Market, "message": err.Error()})
			continue
		}
		if boolFrom(result["ok"], false) {
			items = append(items, result)
		} else {
			failed = append(failed, result)
		}
	}
	return map[string]interface{}{
		"ok": true, "count": len(items), "failedCount": len(failed), "aiAvailable": true,
		"items": items, "failed": failed,
		"message": fmt.Sprintf("完成 %d 只，失败 %d 只", len(items), len(failed)),
	}, nil
}

type watchlistTarget struct {
	ID     *int64
	UserID int64
	Symbol string
	Market string
	Name   string
}

func (s *Service) listEnabledWatchlist(ctx context.Context, userID int64, limit int) ([]watchlistTarget, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT id, user_id, symbol, market, name FROM market_watchlist
WHERE user_id = ? AND enabled = '1' ORDER BY sort_order, create_time LIMIT ?`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []watchlistTarget{}
	for rows.Next() {
		var id, uid sql.NullInt64
		var symbol, marketName, name sql.NullString
		if err := rows.Scan(&id, &uid, &symbol, &marketName, &name); err != nil {
			return nil, err
		}
		var idPtr *int64
		if id.Valid {
			idPtr = &id.Int64
		}
		out = append(out, watchlistTarget{
			ID: idPtr, UserID: uid.Int64,
			Symbol: strings.ToUpper(symbol.String),
			Market: strings.ToUpper(marketName.String),
			Name:   name.String,
		})
	}
	return out, rows.Err()
}

func (s *Service) analyzeWatchlistOne(ctx context.Context, symbol, marketName string, userID int64, watchlistID *int64, name string) (map[string]interface{}, error) {
	if name == "" {
		name = s.resolveInstrumentName(symbol, marketName)
	}
	analyzed, err := s.analyzeSymbol(ctx, symbol, marketName, true, name)
	if err != nil {
		return nil, err
	}
	if !boolFrom(analyzed["ok"], false) {
		return map[string]interface{}{
			"ok": false, "symbol": symbol, "market": marketName,
			"message": stringFrom(analyzed["message"]),
		}, nil
	}
	analysisID, err := s.insertWatchlistAnalysis(ctx, watchlistID, userID, analyzed)
	if err != nil {
		return nil, err
	}
	rec := stringFrom(analyzed["recommendation"])
	if recSign[rec] && userID > 0 {
		level := "success"
		if rec == "减仓" || rec == "卖出" {
			level = "warning"
		}
		_, _ = s.RunUserNotice(ctx, map[string]interface{}{
			"user_id": userID,
			"title":   fmt.Sprintf("自选建议 %s %s", symbol, rec),
			"content": fmt.Sprintf("%s %s · 置信度 %v · %s", symbol, analyzed["stance"], analyzed["confidence"], truncateText(stringFrom(analyzed["summary"]), 180)),
			"level": level, "category": "watchlist",
		})
	}
	return map[string]interface{}{
		"ok": true, "analysisId": analysisID, "symbol": symbol, "market": marketName, "name": name,
		"recommendation": analyzed["recommendation"], "stance": analyzed["stance"], "confidence": analyzed["confidence"],
		"summary": analyzed["summary"], "pickScore": analyzed["pickScore"], "factorScore": analyzed["factorScore"],
		"signal": analyzed["signal"], "message": analyzed["message"],
	}, nil
}

func (s *Service) insertWatchlistAnalysis(ctx context.Context, watchlistID *int64, userID int64, analyzed map[string]interface{}) (int64, error) {
	raw := dumpJSON(map[string]interface{}{
		"recommendation": analyzed["recommendation"], "stance": analyzed["stance"], "confidence": analyzed["confidence"],
		"summary": analyzed["summary"], "indicatorReview": analyzed["indicatorReview"],
		"sentimentReview": analyzed["sentimentReview"], "operationAdvice": analyzed["operationAdvice"],
		"riskWarning": analyzed["riskWarning"], "pickScore": analyzed["pickScore"],
		"factorScore": analyzed["factorScore"], "signal": analyzed["signal"], "source": analyzed["source"],
	}, 60000)
	res, err := s.db.ExecContext(ctx, `
INSERT INTO market_watchlist_analysis (
  watchlist_id, user_id, symbol, market, price, change_percent, stance, recommendation, confidence,
  summary, indicator_review, news_review, sentiment_review, operation_advice, risk_warning,
  source, model_name, indicators_json, news_json, sentiment_json, raw_json, analysis_time
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)`,
		watchlistID, userID, analyzed["symbol"], analyzed["market"], analyzed["price"], analyzed["changePct"],
		analyzed["stance"], analyzed["recommendation"], analyzed["confidence"], analyzed["summary"],
		analyzed["indicatorReview"], analyzed["sentimentReview"], analyzed["operationAdvice"], analyzed["riskWarning"],
		analyzed["source"], analyzed["modelName"], dumpJSON(analyzed["metrics"], 60000),
		dumpJSON(map[string]interface{}{"summary": analyzed["sentimentReview"]}, 60000), raw, nowBeijing(),
	)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func truncateText(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
