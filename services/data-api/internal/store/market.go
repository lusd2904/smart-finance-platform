package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
)

type InstrumentQuery struct {
	Market   string
	Category string
	Enabled  string
	Keyword  string
}

func (d *DB) ListInstruments(ctx context.Context, q InstrumentQuery) ([]map[string]interface{}, error) {
	where := []string{"1=1"}
	args := []interface{}{}
	if q.Market != "" {
		where = append(where, "market = ?")
		args = append(args, strings.ToUpper(q.Market))
	}
	if q.Enabled != "" {
		where = append(where, "enabled = ?")
		args = append(args, q.Enabled)
	}
	if q.Category != "" {
		where = append(where, "category = ?")
		args = append(args, q.Category)
	} else if q.Keyword == "" {
		where = append(where, "category != 'listed'")
	}
	if q.Keyword != "" {
		where = append(where, "(symbol LIKE ? OR name LIKE ?)")
		kw := likeArg(q.Keyword)
		args = append(args, kw, kw)
	}
	limit := ""
	if q.Keyword != "" {
		limit = " LIMIT 200"
	}
	query := fmt.Sprintf(`
SELECT instrument_id, symbol, name, market, category, enabled, create_time
FROM market_instrument WHERE %s ORDER BY category, symbol%s`, strings.Join(where, " AND "), limit)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var id int64
		var symbol, market, category, enabled string
		var name sql.NullString
		var createTime sql.NullTime
		if err := rows.Scan(&id, &symbol, &name, &market, &category, &enabled, &createTime); err != nil {
			return nil, err
		}
		out = append(out, map[string]interface{}{
			"instrumentId": id,
			"symbol":       symbol,
			"name":         nullStr(name),
			"market":       market,
			"category":     category,
			"enabled":      enabled,
			"createTime":   fmtTime(createTime),
		})
	}
	return out, rows.Err()
}

func (d *DB) InstrumentUniverse(ctx context.Context, market, enabled, keyword string, pageNum, pageSize int) (Page, map[string]int, error) {
	where := []string{"1=1"}
	args := []interface{}{}
	if market != "" {
		where = append(where, "market = ?")
		args = append(args, strings.ToUpper(market))
	}
	if enabled != "" {
		where = append(where, "enabled = ?")
		args = append(args, enabled)
	}
	if keyword != "" {
		where = append(where, "(symbol LIKE ? OR name LIKE ?)")
		kw := likeArg(keyword)
		args = append(args, kw, kw)
	}
	w := strings.Join(where, " AND ")
	total, err := countQuery(ctx, d.sql, "SELECT COUNT(*) FROM market_instrument WHERE "+w, args...)
	if err != nil {
		return Page{}, nil, err
	}
	page := paginate(pageNum, pageSize, total)
	offset := (page.PageNum - 1) * page.PageSize
	query := fmt.Sprintf(`
SELECT instrument_id, symbol, name, market, category, enabled, create_time
FROM market_instrument WHERE %s
ORDER BY category = 'listed', market, symbol LIMIT ? OFFSET ?`, w)
	args = append(args, page.PageSize, offset)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return Page{}, nil, err
	}
	defer rows.Close()
	page.Rows = []map[string]interface{}{}
	for rows.Next() {
		var id int64
		var symbol, marketVal, category, enabledVal string
		var name sql.NullString
		var createTime sql.NullTime
		if err := rows.Scan(&id, &symbol, &name, &marketVal, &category, &enabledVal, &createTime); err != nil {
			return Page{}, nil, err
		}
		page.Rows = append(page.Rows, map[string]interface{}{
			"instrumentId": id,
			"symbol":       symbol,
			"name":         nullStr(name),
			"market":       marketVal,
			"category":     category,
			"enabled":      enabledVal,
			"createTime":   fmtTime(createTime),
		})
	}
	counts, _ := d.instrumentMarketCounts(ctx, enabled)
	return page, counts, rows.Err()
}

func (d *DB) instrumentMarketCounts(ctx context.Context, enabled string) (map[string]int, error) {
	query := "SELECT market, COUNT(*) FROM market_instrument"
	args := []interface{}{}
	if enabled != "" {
		query += " WHERE enabled = ?"
		args = append(args, enabled)
	}
	query += " GROUP BY market"
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	counts := map[string]int{"US": 0, "HK": 0, "CN": 0, "total": 0}
	for rows.Next() {
		var market string
		var n int
		if err := rows.Scan(&market, &n); err != nil {
			return counts, err
		}
		key := strings.ToUpper(market)
		if _, ok := counts[key]; ok {
			counts[key] = n
		}
		counts["total"] += n
	}
	return counts, rows.Err()
}

func (d *DB) ListFinanceBriefings(ctx context.Context, market, symbol string, limit int) ([]map[string]interface{}, error) {
	if limit < 1 {
		limit = 20
	}
	if limit > 60 {
		limit = 60
	}
	where := []string{"1=1"}
	args := []interface{}{}
	if market != "" {
		where = append(where, "market = ?")
		args = append(args, strings.ToUpper(market))
	}
	if symbol != "" {
		where = append(where, "(headline LIKE ? OR summary LIKE ?)")
		kw := likeArg(symbol)
		args = append(args, kw, kw)
	}
	query := fmt.Sprintf(`
SELECT id, market, briefing_type, headline, summary, source_name, source_link,
       payload_json, generated_at, expires_at
FROM finance_briefing WHERE %s ORDER BY generated_at DESC LIMIT ?`, strings.Join(where, " AND "))
	args = append(args, limit)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	for rows.Next() {
		var id int64
		var marketVal, briefingType, headline, sourceName string
		var summary, sourceLink, payloadJSON sql.NullString
		var generatedAt sql.NullTime
		var expiresAt sql.NullTime
		if err := rows.Scan(&id, &marketVal, &briefingType, &headline, &summary, &sourceName, &sourceLink,
			&payloadJSON, &generatedAt, &expiresAt); err != nil {
			return nil, err
		}
		item := map[string]interface{}{
			"id":            id,
			"market":        marketVal,
			"briefingType":  briefingType,
			"headline":      headline,
			"summary":       nullStr(summary),
			"sourceName":    sourceName,
			"sourceLink":    nullStr(sourceLink),
			"generatedAt":   fmtTime(generatedAt),
			"expiresAt":     fmtTime(expiresAt),
		}
		if payloadJSON.Valid && payloadJSON.String != "" {
			var payload map[string]interface{}
			if json.Unmarshal([]byte(payloadJSON.String), &payload) == nil {
				item["payload"] = payload
			}
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

func (d *DB) ListReviewLatest(ctx context.Context) ([]map[string]interface{}, error) {
	query := `
SELECT review_id, market, trade_date, title, summary, stance, heat_score, index_change_pct,
       model_name, analysis_time, status, message
FROM market_daily_review r
WHERE review_id IN (
  SELECT MAX(review_id) FROM market_daily_review GROUP BY market
) ORDER BY FIELD(market, 'US', 'HK', 'CN')`
	rows, err := d.sql.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanReviews(rows)
}

func (d *DB) ListReviewHistory(ctx context.Context, market string, limit int) ([]map[string]interface{}, error) {
	if limit < 1 {
		limit = 60
	}
	where := "1=1"
	args := []interface{}{}
	if market != "" {
		where = "market = ?"
		args = append(args, strings.ToUpper(market))
	}
	query := fmt.Sprintf(`
SELECT review_id, market, trade_date, title, summary, stance, heat_score, index_change_pct,
       model_name, analysis_time, status, message
FROM market_daily_review WHERE %s ORDER BY trade_date DESC, review_id DESC LIMIT ?`, where)
	args = append(args, limit)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanReviews(rows)
}

func scanReviews(rows *sql.Rows) ([]map[string]interface{}, error) {
	out := []map[string]interface{}{}
	for rows.Next() {
		var id int64
		var market, tradeDate, title string
		var summary, stance, modelName, status, message sql.NullString
		var heatScore, indexChange sql.NullFloat64
		var analysisTime sql.NullTime
		if err := rows.Scan(&id, &market, &tradeDate, &title, &summary, &stance, &heatScore, &indexChange,
			&modelName, &analysisTime, &status, &message); err != nil {
			return nil, err
		}
		out = append(out, map[string]interface{}{
			"reviewId":        id,
			"market":          market,
			"tradeDate":       tradeDate,
			"title":           title,
			"summary":         nullStr(summary),
			"stance":          nullStr(stance),
			"heatScore":       nullFloat(heatScore),
			"indexChangePct":  nullFloat(indexChange),
			"modelName":       nullStr(modelName),
			"analysisTime":    fmtTime(analysisTime),
			"status":          nullStr(status),
			"message":         nullStr(message),
		})
	}
	return out, rows.Err()
}

func (d *DB) WatchlistPage(ctx context.Context, userID int64, symbol, market, enabled string, pageNum, pageSize int) (Page, error) {
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
	total, err := countQuery(ctx, d.sql, "SELECT COUNT(*) FROM market_watchlist WHERE "+w, args...)
	if err != nil {
		return Page{}, err
	}
	page := paginate(pageNum, pageSize, total)
	offset := (page.PageNum - 1) * page.PageSize
	query := fmt.Sprintf(`
SELECT id, user_id, symbol, market, name, note, enabled, sort_order, create_time, update_time
FROM market_watchlist WHERE %s ORDER BY sort_order, create_time DESC LIMIT ? OFFSET ?`, w)
	args = append(args, page.PageSize, offset)
	rows, err := d.sql.QueryContext(ctx, query, args...)
	if err != nil {
		return Page{}, err
	}
	defer rows.Close()
	page.Rows = []map[string]interface{}{}
	for rows.Next() {
		var id, userIDVal int64
		var symbolVal, marketVal, enabledVal string
		var name, note sql.NullString
		var sortOrder int
		var createTime, updateTime sql.NullTime
		if err := rows.Scan(&id, &userIDVal, &symbolVal, &marketVal, &name, &note, &enabledVal, &sortOrder, &createTime, &updateTime); err != nil {
			return Page{}, err
		}
		page.Rows = append(page.Rows, map[string]interface{}{
			"id":         id,
			"userId":     userIDVal,
			"symbol":     symbolVal,
			"market":     marketVal,
			"name":       nullStr(name),
			"note":       nullStr(note),
			"enabled":    enabledVal,
			"sortOrder":  sortOrder,
			"createTime": fmtTime(createTime),
			"updateTime": fmtTime(updateTime),
		})
	}
	return page, rows.Err()
}

func (d *DB) WatchlistEnabled(ctx context.Context, userID int64) ([]map[string]interface{}, error) {
	rows, err := d.sql.QueryContext(ctx, `
SELECT id, user_id, symbol, market, name, note, enabled, sort_order, create_time
FROM market_watchlist WHERE user_id = ? AND enabled = '1' ORDER BY sort_order, create_time`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var id, uid int64
		var symbol, market, enabled string
		var name, note sql.NullString
		var sortOrder int
		var createTime sql.NullTime
		if err := rows.Scan(&id, &uid, &symbol, &market, &name, &note, &enabled, &sortOrder, &createTime); err != nil {
			return nil, err
		}
		out = append(out, map[string]interface{}{
			"id": id, "userId": uid, "symbol": symbol, "market": market,
			"name": nullStr(name), "note": nullStr(note), "enabled": enabled,
			"sortOrder": sortOrder, "createTime": fmtTime(createTime),
		})
	}
	return out, rows.Err()
}

func (d *DB) AddWatchlist(ctx context.Context, userID int64, symbol, market, name, note string) error {
	_, err := d.sql.ExecContext(ctx, `
INSERT INTO market_watchlist (user_id, symbol, market, name, note, enabled, sort_order, create_time, update_time)
VALUES (?, ?, ?, ?, ?, '1', 0, NOW(), NOW())
ON DUPLICATE KEY UPDATE name=VALUES(name), note=VALUES(note), enabled='1', update_time=NOW()`,
		userID, strings.ToUpper(symbol), strings.ToUpper(market), name, note)
	return err
}

func (d *DB) DeleteWatchlist(ctx context.Context, userID int64, ids []int64) (int64, error) {
	if len(ids) == 0 {
		return 0, nil
	}
	placeholders := strings.Repeat("?,", len(ids))
	placeholders = placeholders[:len(placeholders)-1]
	args := []interface{}{userID}
	for _, id := range ids {
		args = append(args, id)
	}
	res, err := d.sql.ExecContext(ctx,
		fmt.Sprintf("DELETE FROM market_watchlist WHERE user_id = ? AND id IN (%s)", placeholders), args...)
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}

func (d *DB) WatchlistAnalysisHistory(ctx context.Context, userID int64, symbol, market string, limit int) ([]map[string]interface{}, error) {
	if limit < 1 {
		limit = 24
	}
	rows, err := d.sql.QueryContext(ctx, `
SELECT analysis_id, symbol, market, price, change_percent, stance, recommendation, confidence,
       summary, analysis_time, source, model_name
FROM market_watchlist_analysis
WHERE user_id = ? AND symbol = ? AND market = ?
ORDER BY analysis_time DESC LIMIT ?`, userID, strings.ToUpper(symbol), strings.ToUpper(market), limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]interface{}{}
	for rows.Next() {
		var analysisID int64
		var symbolVal, marketVal string
		var price, changePct sql.NullFloat64
		var stance, recommendation, summary, source, modelName sql.NullString
		var confidence sql.NullInt64
		var analysisTime sql.NullTime
		if err := rows.Scan(&analysisID, &symbolVal, &marketVal, &price, &changePct, &stance, &recommendation,
			&confidence, &summary, &analysisTime, &source, &modelName); err != nil {
			return nil, err
		}
		out = append(out, map[string]interface{}{
			"analysisId":     analysisID,
			"symbol":         symbolVal,
			"market":         marketVal,
			"price":          nullFloat(price),
			"changePercent":  nullFloat(changePct),
			"stance":         nullStr(stance),
			"recommendation": nullStr(recommendation),
			"confidence":     nullInt(confidence),
			"summary":        nullStr(summary),
			"analysisTime":   fmtTime(analysisTime),
			"source":         nullStr(source),
			"modelName":      nullStr(modelName),
		})
	}
	return out, rows.Err()
}

func (d *DB) LatestWatchlistAnalysis(ctx context.Context, userID int64, symbol, market string) (map[string]interface{}, error) {
	rows, err := d.WatchlistAnalysisHistory(ctx, userID, symbol, market, 1)
	if err != nil || len(rows) == 0 {
		return nil, err
	}
	return rows[0], nil
}

func (d *DB) GetInstrumentBySymbol(ctx context.Context, symbol string) (map[string]interface{}, error) {
	var id int64
	var sym, marketVal, category, enabled string
	var name sql.NullString
	var createTime sql.NullTime
	err := d.sql.QueryRowContext(ctx, `
SELECT instrument_id, symbol, name, market, category, enabled, create_time
FROM market_instrument WHERE symbol = ?`, strings.ToUpper(symbol)).Scan(
		&id, &sym, &name, &marketVal, &category, &enabled, &createTime)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"instrumentId": id, "symbol": sym, "name": nullStr(name),
		"market": marketVal, "category": category, "enabled": enabled,
		"createTime": fmtTime(createTime),
	}, nil
}

func (d *DB) LatestAIAnalysis(ctx context.Context, symbol, market string) (map[string]interface{}, error) {
	var analysisID int64
	var sym, marketVal string
	var price sql.NullFloat64
	var finalDecision sql.NullString
	var finalConfidence sql.NullInt64
	var summaryText, indicatorsJSON, rawJSON, modelName sql.NullString
	var analysisTime sql.NullTime
	err := d.sql.QueryRowContext(ctx, `
SELECT analysis_id, symbol, market, price, final_decision, final_confidence, summary_text,
       indicators_json, raw_json, model_name, analysis_time
FROM symbol_ai_analysis WHERE symbol = ? AND market = ?
ORDER BY analysis_time DESC, analysis_id DESC LIMIT 1`,
		strings.ToUpper(symbol), strings.ToUpper(market)).Scan(
		&analysisID, &sym, &marketVal, &price, &finalDecision, &finalConfidence, &summaryText,
		&indicatorsJSON, &rawJSON, &modelName, &analysisTime)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	result := map[string]interface{}{
		"analysisId": analysisID, "symbol": sym, "market": marketVal,
		"price": nullFloat(price), "finalDecision": nullStr(finalDecision),
		"finalConfidence": nullInt(finalConfidence), "summaryText": nullStr(summaryText),
		"modelName": nullStr(modelName), "analysisTime": fmtTime(analysisTime),
	}
	if indicatorsJSON.Valid && indicatorsJSON.String != "" {
		var ind map[string]interface{}
		if json.Unmarshal([]byte(indicatorsJSON.String), &ind) == nil {
			result["indicators"] = ind
			result["metrics"] = ind
		}
	}
	if rawJSON.Valid && rawJSON.String != "" {
		var raw map[string]interface{}
		if json.Unmarshal([]byte(rawJSON.String), &raw) == nil {
			result["raw"] = raw
			if adv, ok := raw["operationAdvice"]; ok {
				result["advice"] = adv
			}
		}
	}
	return result, nil
}

func (d *DB) StockPickDates(ctx context.Context, limit int) (map[string]interface{}, error) {
	if limit < 1 {
		limit = 60
	}
	rows, err := d.sql.QueryContext(ctx, `
SELECT pick_id, trade_date, status, picked_count, ai_count, model_name, update_time
FROM market_stock_pick ORDER BY trade_date DESC, pick_id DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	dates := []map[string]interface{}{}
	var defaultDate string
	for rows.Next() {
		var pickID int64
		var tradeDate, status string
		var pickedCount, aiCount int
		var modelName sql.NullString
		var updateTime sql.NullTime
		if err := rows.Scan(&pickID, &tradeDate, &status, &pickedCount, &aiCount, &modelName, &updateTime); err != nil {
			return nil, err
		}
		if defaultDate == "" {
			defaultDate = tradeDate
		}
		dates = append(dates, map[string]interface{}{
			"id": pickID, "tradeDate": tradeDate, "status": status,
			"pickedCount": pickedCount, "aiCount": aiCount, "modelName": nullStr(modelName),
			"updatedAt": fmtTime(updateTime), "hasPickSheet": true,
		})
	}
	return map[string]interface{}{"dates": dates, "defaultTradeDate": defaultDate}, rows.Err()
}

func (d *DB) StockPickLatest(ctx context.Context, market, tradeDate string) (map[string]interface{}, error) {
	var pickID int64
	var tradeDay, status string
	var pickedCount, aiCount int
	var modelName, summary sql.NullString
	var updateTime sql.NullTime
	query := `
SELECT pick_id, trade_date, status, picked_count, ai_count, model_name, summary_text, update_time
FROM market_stock_pick`
	args := []interface{}{}
	if tradeDate != "" {
		query += " WHERE trade_date = ?"
		args = append(args, tradeDate[:10])
	} else {
		query += " ORDER BY trade_date DESC, pick_id DESC LIMIT 1"
	}
	if tradeDate != "" {
		query += " LIMIT 1"
	}
	err := d.sql.QueryRowContext(ctx, query, args...).Scan(
		&pickID, &tradeDay, &status, &pickedCount, &aiCount, &modelName, &summary, &updateTime)
	if err == sql.ErrNoRows {
		return map[string]interface{}{"empty": true, "tradeDate": tradeDate}, nil
	}
	if err != nil {
		return nil, err
	}
	itemQuery := `
SELECT symbol, market, name, rank_no, score, reason, ai_pick, tags_json
FROM market_stock_pick_item WHERE pick_id = ?`
	itemArgs := []interface{}{pickID}
	if market != "" {
		itemQuery += " AND market = ?"
		itemArgs = append(itemArgs, strings.ToUpper(market))
	}
	itemQuery += " ORDER BY market, rank_no"
	itemRows, err := d.sql.QueryContext(ctx, itemQuery, itemArgs...)
	if err != nil {
		return nil, err
	}
	defer itemRows.Close()
	items := []map[string]interface{}{}
	for itemRows.Next() {
		var symbolVal, marketVal, name, reason, tagsJSON sql.NullString
		var rankNo int
		var score sql.NullFloat64
		var aiPick sql.NullString
		if err := itemRows.Scan(&symbolVal, &marketVal, &name, &rankNo, &score, &reason, &aiPick, &tagsJSON); err != nil {
			return nil, err
		}
		item := map[string]interface{}{
			"symbol": symbolVal.String, "market": marketVal.String, "name": nullStr(name),
			"rankNo": rankNo, "score": nullFloat(score), "reason": nullStr(reason),
			"aiPick": aiPick.String == "1",
		}
		if tagsJSON.Valid && tagsJSON.String != "" {
			var tags []interface{}
			if json.Unmarshal([]byte(tagsJSON.String), &tags) == nil {
				item["tags"] = tags
			}
		}
		items = append(items, item)
	}
	return map[string]interface{}{
		"pickId": pickID, "tradeDate": tradeDay, "status": status,
		"pickedCount": pickedCount, "aiCount": aiCount, "modelName": nullStr(modelName),
		"summary": nullStr(summary), "updatedAt": fmtTime(updateTime), "items": items,
	}, itemRows.Err()
}

func (d *DB) StockPickMood(ctx context.Context) (map[string]interface{}, error) {
	heats := map[string]interface{}{}
	for _, m := range []string{"US", "HK", "CN"} {
		var tradeDate sql.NullString
		var heatScore sql.NullFloat64
		var heatSummary sql.NullString
		err := d.sql.QueryRowContext(ctx, `
SELECT trade_date, heat_score, heat_summary FROM market_heat_daily
WHERE market = ? ORDER BY trade_date DESC LIMIT 1`, m).Scan(&tradeDate, &heatScore, &heatSummary)
		if err == nil {
			heats[m] = map[string]interface{}{
				"market": m, "tradeDate": nullStr(tradeDate),
				"heatScore": nullFloat(heatScore), "heatSummary": nullStr(heatSummary),
			}
		}
	}
	return map[string]interface{}{
		"sessions":     map[string]interface{}{"US": map[string]interface{}{"open": false}, "HK": map[string]interface{}{"open": false}, "CN": map[string]interface{}{"open": false}},
		"openMarkets":  []string{},
		"indices":      []interface{}{},
		"sentiment":    nil,
		"heat":         heats,
		"headlines":    []interface{}{},
		"hint":         "Go data-api 简化版：会话/指数需 jobs 预热或 legacy Python",
		"degraded":     true,
	}, nil
}
