package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"
)

func (d *DB) ListFactorSnapshots(ctx context.Context, limit int) ([]map[string]interface{}, error) {
	if limit < 1 {
		limit = 80
	}
	rows, err := d.sql.QueryContext(ctx, `
SELECT symbol, market, as_of, score_total, risk_level, trend_direction, alpha101_count,
       alpha158_count, alpha_json, create_time
FROM quant_factor_snapshot ORDER BY create_time DESC, snapshot_id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	for rows.Next() {
		var symbol, market string
		var asOf sql.NullString
		var scoreTotal sql.NullFloat64
		var riskLevel, trendDirection sql.NullString
		var alpha101Count, alpha158Count sql.NullInt64
		var alphaJSON sql.NullString
		var createTime sql.NullTime
		if err := rows.Scan(&symbol, &market, &asOf, &scoreTotal, &riskLevel, &trendDirection,
			&alpha101Count, &alpha158Count, &alphaJSON, &createTime); err != nil {
			return nil, err
		}
		alphaCs := map[string]interface{}{}
		if alphaJSON.Valid && alphaJSON.String != "" {
			var alpha map[string]interface{}
			if json.Unmarshal([]byte(alphaJSON.String), &alpha) == nil {
				if cs, ok := alpha["alphaCs"].(map[string]interface{}); ok {
					alphaCs = cs
				}
			}
		}
		items = append(items, map[string]interface{}{
			"symbol": symbol, "market": market, "asOf": nullStr(asOf),
			"total": nullFloat(scoreTotal), "riskLevel": nullStr(riskLevel),
			"trendDirection": nullStr(trendDirection), "alpha101Count": nullInt(alpha101Count),
			"alpha158Count": nullInt(alpha158Count), "alphaCsCount": len(alphaCs),
			"alphaCs": alphaCs, "createTime": fmtTime(createTime),
		})
	}
	return items, rows.Err()
}

func (d *DB) FactorQCReport(ctx context.Context, market string) (map[string]interface{}, error) {
	rows, err := d.sql.QueryContext(ctx, `
SELECT factor_key, factor_label, horizon, ic_mean, ic_std, ir, spread, sample_dates,
       symbol_count, quantile_json, payload_json, as_of, create_time
FROM quant_factor_qc WHERE market = ? ORDER BY create_time DESC LIMIT 200`, strings.ToUpper(market))
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	var asOf interface{}
	for rows.Next() {
		var factorKey, factorLabel, horizon string
		var icMean, icStd, ir, spread sql.NullFloat64
		var sampleDates, symbolCount sql.NullInt64
		var quantileJSON, payloadJSON sql.NullString
		var asOfVal sql.NullString
		var createTime sql.NullTime
		if err := rows.Scan(&factorKey, &factorLabel, &horizon, &icMean, &icStd, &ir, &spread,
			&sampleDates, &symbolCount, &quantileJSON, &payloadJSON, &asOfVal, &createTime); err != nil {
			return nil, err
		}
		quantiles := map[string]interface{}{}
		if quantileJSON.Valid && quantileJSON.String != "" {
			_ = json.Unmarshal([]byte(quantileJSON.String), &quantiles)
		}
		payload := map[string]interface{}{}
		if payloadJSON.Valid && payloadJSON.String != "" {
			_ = json.Unmarshal([]byte(payloadJSON.String), &payload)
		}
		item := map[string]interface{}{
			"factorKey": factorKey, "factorLabel": factorLabel,
			"family": payload["family"], "horizon": horizon,
			"icMean": nullFloat(icMean), "icStd": nullFloat(icStd), "ir": nullFloat(ir),
			"spread": nullFloat(spread), "sampleDates": nullInt(sampleDates),
			"symbolCount": nullInt(symbolCount), "quantiles": quantiles,
			"icPositiveRatio": payload["icPositiveRatio"], "ok": payload["ok"],
			"asOf": nullStr(asOfVal), "createTime": fmtTime(createTime),
		}
		items = append(items, item)
		if asOf == nil {
			asOf = nullStr(asOfVal)
		}
	}
	msg := "暂无质检结果，请先运行因子质检"
	if len(items) > 0 {
		msg = "已加载最近一次质检"
	}
	return map[string]interface{}{
		"ok": len(items) > 0, "engine": "alphalens-style-v1", "market": strings.ToUpper(market),
		"asOf": asOf, "itemCount": len(items), "items": items, "message": msg,
	}, rows.Err()
}

func (d *DB) QuantWatchlistPage(ctx context.Context, userID int64, symbol, market, enabled string, pageNum, pageSize int) (Page, error) {
	where := []string{"user_id = ?"}
	args := []interface{}{userID}
	if symbol != "" {
		where = append(where, "symbol LIKE ?")
		args = append(args, likeArg(symbol))
	}
	if market != "" {
		where = append(where, "market = ?")
		args = append(args, strings.ToUpper(market))
	}
	if enabled != "" {
		where = append(where, "enabled = ?")
		args = append(args, enabled)
	}
	w := strings.Join(where, " AND ")
	total, err := countQuery(ctx, d.sql, "SELECT COUNT(*) FROM quant_watchlist WHERE "+w, args...)
	if err != nil {
		return Page{}, err
	}
	page := paginate(pageNum, pageSize, total)
	offset := (page.PageNum - 1) * page.PageSize
	query := fmt.Sprintf(`
SELECT id, user_id, symbol, market, note, enabled, create_time
FROM quant_watchlist WHERE %s ORDER BY create_time DESC LIMIT ? OFFSET ?`, w)
	args = append(args, page.PageSize, offset)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return Page{}, err
	}
	defer rows.Close()
	page.Rows = []map[string]interface{}{}
	for rows.Next() {
		var id, uid int64
		var symbolVal, marketVal, enabledVal string
		var note sql.NullString
		var createTime sql.NullTime
		if err := rows.Scan(&id, &uid, &symbolVal, &marketVal, &note, &enabledVal, &createTime); err != nil {
			return Page{}, err
		}
		page.Rows = append(page.Rows, map[string]interface{}{
			"id": id, "userId": uid, "symbol": symbolVal, "market": marketVal,
			"note": nullStr(note), "enabled": enabledVal, "createTime": fmtTime(createTime),
		})
	}
	return page, rows.Err()
}

func (d *DB) AddQuantWatchlist(ctx context.Context, userID int64, symbol, market, note string) error {
	_, err := d.sql.ExecContext(ctx, `
INSERT INTO quant_watchlist (user_id, symbol, market, note, enabled, create_time)
VALUES (?, ?, ?, ?, '1', NOW())
ON DUPLICATE KEY UPDATE note=VALUES(note), enabled='1'`,
		userID, strings.ToUpper(symbol), strings.ToUpper(market), note)
	return err
}

func (d *DB) DeleteQuantWatchlist(ctx context.Context, userID int64, ids []int64) error {
	if len(ids) == 0 {
		return nil
	}
	placeholders := strings.Repeat("?,", len(ids))
	placeholders = placeholders[:len(placeholders)-1]
	args := []interface{}{userID}
	for _, id := range ids {
		args = append(args, id)
	}
	_, err := d.sql.ExecContext(ctx,
		fmt.Sprintf("DELETE FROM quant_watchlist WHERE user_id = ? AND id IN (%s)", placeholders), args...)
	return err
}

func (d *DB) StrategyHistoryPage(ctx context.Context, userID int64, profile, begin, end string, pageNum, pageSize int) (Page, error) {
	where := []string{"user_id = ?"}
	args := []interface{}{userID}
	if profile != "" {
		where = append(where, "strategy_profile = ?")
		args = append(args, profile)
	}
	if begin != "" && end != "" {
		where = append(where, "create_time BETWEEN ? AND ?")
		args = append(args, begin+" 00:00:00", end+" 23:59:59")
	}
	w := strings.Join(where, " AND ")
	total, err := countQuery(ctx, d.sql, "SELECT COUNT(*) FROM quant_strategy_run WHERE "+w, args...)
	if err != nil {
		return Page{}, err
	}
	page := paginate(pageNum, pageSize, total)
	offset := (page.PageNum - 1) * page.PageSize
	query := fmt.Sprintf(`
SELECT run_id, cycle_id, user_id, strategy_profile, symbols_count, signal_count, create_time
FROM quant_strategy_run WHERE %s ORDER BY create_time DESC LIMIT ? OFFSET ?`, w)
	args = append(args, page.PageSize, offset)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return Page{}, err
	}
	defer rows.Close()
	page.Rows = []map[string]interface{}{}
	for rows.Next() {
		var runID, uid int64
		var cycleID, profileVal sql.NullString
		var symbolsCount, signalCount int
		var createTime sql.NullTime
		if err := rows.Scan(&runID, &cycleID, &uid, &profileVal, &symbolsCount, &signalCount, &createTime); err != nil {
			return Page{}, err
		}
		page.Rows = append(page.Rows, map[string]interface{}{
			"runId": runID, "cycleId": nullStr(cycleID), "userId": uid,
			"strategyProfile": nullStr(profileVal), "symbolsCount": symbolsCount,
			"signalCount": signalCount, "createTime": fmtTime(createTime),
		})
	}
	return page, rows.Err()
}

func (d *DB) ScanRuns(ctx context.Context, userID int64, limit int) (map[string]interface{}, error) {
	if limit < 1 {
		limit = 20
	}
	if limit > 100 {
		limit = 100
	}
	rows, err := d.sql.QueryContext(ctx, `
SELECT run_id, cycle_id, strategy_profile, symbols_count, signal_count, create_time
FROM quant_strategy_run WHERE user_id = ? ORDER BY create_time DESC LIMIT ?`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	opportunityTotal := 0
	for rows.Next() {
		var runID int64
		var cycleID, profile sql.NullString
		var symbolsCount, signalCount int
		var createTime sql.NullTime
		if err := rows.Scan(&runID, &cycleID, &profile, &symbolsCount, &signalCount, &createTime); err != nil {
			return nil, err
		}
		started := fmtTime(createTime)
		items = append(items, map[string]interface{}{
			"runId": runID, "cycleId": nullStr(cycleID), "status": "completed",
			"reason": "executed", "message": fmt.Sprintf("评估%d个标的，产出%d个可执行信号", symbolsCount, signalCount),
			"strategyProfile": nullStr(profile), "targetCount": symbolsCount, "evaluatedCount": symbolsCount,
			"opportunityCount": signalCount, "submittedCount": 0, "skippedCount": 0,
			"signalCount": signalCount, "startedAt": started, "finishedAt": started,
			"source": "manual_or_scheduler",
		})
		opportunityTotal += signalCount
	}
	return map[string]interface{}{
		"items": items,
		"summary": map[string]interface{}{
			"recordCount": len(items), "completedCount": len(items),
			"opportunityCount": opportunityTotal, "submittedCount": 0,
		},
		"limit": limit,
	}, rows.Err()
}

func (d *DB) ScanRunDetail(ctx context.Context, cycleOrRunID string) (map[string]interface{}, error) {
	var runID int64
	var cycleID, profile sql.NullString
	var symbolsCount, signalCount int
	var createTime sql.NullTime
	var err error
	if isDigits(cycleOrRunID) {
		err = d.sql.QueryRowContext(ctx, `
SELECT run_id, cycle_id, strategy_profile, symbols_count, signal_count, create_time
FROM quant_strategy_run WHERE run_id = ?`, cycleOrRunID).Scan(
			&runID, &cycleID, &profile, &symbolsCount, &signalCount, &createTime)
	}
	if err == sql.ErrNoRows || !isDigits(cycleOrRunID) {
		err = d.sql.QueryRowContext(ctx, `
SELECT run_id, cycle_id, strategy_profile, symbols_count, signal_count, create_time
FROM quant_strategy_run WHERE cycle_id = ? ORDER BY create_time DESC LIMIT 1`, cycleOrRunID).Scan(
			&runID, &cycleID, &profile, &symbolsCount, &signalCount, &createTime)
	}
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("扫描记录不存在")
	}
	if err != nil {
		return nil, err
	}
	sigRows, err := d.sql.QueryContext(context.Background(), `
SELECT symbol, signal, score, confidence, reason, factor_json
FROM quant_strategy_signal WHERE run_id = ? ORDER BY score DESC`, runID)
	if err != nil {
		return nil, err
	}
	defer sigRows.Close()
	opportunities := []map[string]interface{}{}
	candidates := []map[string]interface{}{}
	skipped := []map[string]interface{}{}
	for sigRows.Next() {
		var symbol, signalVal string
		var score sql.NullFloat64
		var confidence sql.NullInt64
		var reason, factorJSON sql.NullString
		if err := sigRows.Scan(&symbol, &signalVal, &score, &confidence, &reason, &factorJSON); err != nil {
			return nil, err
		}
		factor := map[string]interface{}{}
		if factorJSON.Valid && factorJSON.String != "" {
			_ = json.Unmarshal([]byte(factorJSON.String), &factor)
		}
		scoreObj, _ := factor["score"].(map[string]interface{})
		row := map[string]interface{}{
			"symbol": symbol, "side": signalVal, "isOpportunity": signalVal == "BUY",
			"confidence": nullInt(confidence), "score": nullFloat(score),
			"riskLevel": scoreObj["riskLevel"], "reason": nullStr(reason),
		}
		candidates = append(candidates, row)
		if signalVal == "BUY" {
			opportunities = append(opportunities, row)
		} else {
			skipped = append(skipped, map[string]interface{}{
				"symbol": symbol, "skipReason": nullStr(reason),
			})
		}
	}
	started := fmtTime(createTime)
	return map[string]interface{}{
		"runId": runID, "cycleId": nullStr(cycleID), "strategyProfile": nullStr(profile),
		"status": "completed", "targetCount": symbolsCount, "evaluatedCount": symbolsCount,
		"opportunityCount": len(opportunities), "signalCount": signalCount,
		"startedAt": started, "finishedAt": started,
		"candidates": candidates, "opportunities": opportunities, "skipped": skipped,
	}, sigRows.Err()
}

func (d *DB) SymbolLatestScan(ctx context.Context, userID int64, symbol, market string) (map[string]interface{}, error) {
	var runID int64
	var cycleID sql.NullString
	var profile sql.NullString
	var signalVal string
	var score sql.NullFloat64
	var confidence sql.NullInt64
	var reason, factorJSON sql.NullString
	var createTime sql.NullTime
	err := d.sql.QueryRowContext(ctx, `
SELECT s.run_id, r.cycle_id, r.strategy_profile, s.signal, s.score, s.confidence, s.reason, s.factor_json, s.create_time
FROM quant_strategy_signal s
JOIN quant_strategy_run r ON r.run_id = s.run_id
WHERE s.user_id = ? AND s.symbol = ? AND r.strategy_profile IS NOT NULL
ORDER BY s.create_time DESC LIMIT 1`, userID, strings.ToUpper(symbol)).Scan(
		&runID, &cycleID, &profile, &signalVal, &score, &confidence, &reason, &factorJSON, &createTime)
	if err == sql.ErrNoRows {
		return map[string]interface{}{
			"symbol": strings.ToUpper(symbol), "market": strings.ToUpper(market),
			"empty": true, "message": "暂无扫描记录",
		}, nil
	}
	if err != nil {
		return nil, err
	}
	factor := map[string]interface{}{}
	if factorJSON.Valid && factorJSON.String != "" {
		_ = json.Unmarshal([]byte(factorJSON.String), &factor)
	}
	return map[string]interface{}{
		"symbol": strings.ToUpper(symbol), "market": strings.ToUpper(market),
		"runId": runID, "cycleId": nullStr(cycleID), "strategyProfile": nullStr(profile),
		"signal": signalVal, "score": nullFloat(score), "confidence": nullInt(confidence),
		"reason": nullStr(reason), "factor": factor, "createTime": fmtTime(createTime),
	}, nil
}

func (d *DB) DailyListLatest(ctx context.Context, userID int64) (map[string]interface{}, error) {
	var listID int64
	var scanDate, tradeDate time.Time
	var profile, status string
	var autoEnabled string
	var itemCount int
	var message sql.NullString
	var createTime, updateTime sql.NullTime
	err := d.sql.QueryRowContext(ctx, `
SELECT list_id, scan_date, trade_date, profile, status, auto_enabled, item_count, message, create_time, update_time
FROM quant_daily_list WHERE user_id = ? ORDER BY trade_date DESC, list_id DESC LIMIT 1`, userID).Scan(
		&listID, &scanDate, &tradeDate, &profile, &status, &autoEnabled, &itemCount, &message, &createTime, &updateTime)
	if err == sql.ErrNoRows {
		return map[string]interface{}{"empty": true, "message": "暂无次日策略清单"}, nil
	}
	if err != nil {
		return nil, err
	}
	itemRows, err := d.sql.QueryContext(ctx, `
SELECT item_id, symbol, market, name, signal, score, confidence, reason, selected, auto_trade, status, side
FROM quant_daily_list_item WHERE list_id = ? ORDER BY score DESC`, listID)
	if err != nil {
		return nil, err
	}
	defer itemRows.Close()
	items := []map[string]interface{}{}
	for itemRows.Next() {
		var itemID int64
		var symbolVal, marketVal, signalVal, statusVal, side string
		var name, reason sql.NullString
		var score sql.NullFloat64
		var confidence sql.NullInt64
		var selected, autoTrade string
		if err := itemRows.Scan(&itemID, &symbolVal, &marketVal, &name, &signalVal, &score, &confidence,
			&reason, &selected, &autoTrade, &statusVal, &side); err != nil {
			return nil, err
		}
		items = append(items, map[string]interface{}{
			"itemId": itemID, "symbol": symbolVal, "market": marketVal, "name": nullStr(name),
			"signal": signalVal, "score": nullFloat(score), "confidence": nullInt(confidence),
			"reason": nullStr(reason), "selected": selected == "1", "autoTrade": autoTrade == "1",
			"status": statusVal, "side": side,
		})
	}
	return map[string]interface{}{
		"list": map[string]interface{}{
			"listId": listID, "scanDate": scanDate.Format("2006-01-02"),
			"tradeDate": tradeDate.Format("2006-01-02"), "profile": profile, "status": status,
			"autoEnabled": autoEnabled == "1", "itemCount": itemCount, "message": nullStr(message),
			"createTime": fmtTime(createTime), "updateTime": fmtTime(updateTime), "items": items,
		},
	}, itemRows.Err()
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}
