package jobs

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
)

type Repo struct {
	DB *sql.DB
}

func (r *Repo) ListConfiguredUserIDs(ctx context.Context) ([]int, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT user_id FROM quant_longbridge_config
WHERE app_key IS NOT NULL AND app_key <> ''
  AND access_token IS NOT NULL AND access_token <> ''`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int
	for rows.Next() {
		var id int
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		ids = append(ids, id)
	}
	return ids, rows.Err()
}

func (r *Repo) DistinctWatchlistUsers(ctx context.Context) ([]int, error) {
	rows, err := r.DB.QueryContext(ctx, `SELECT DISTINCT user_id FROM market_watchlist WHERE enabled = '1'`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var ids []int
	for rows.Next() {
		var id int
		if err := rows.Scan(&id); err != nil {
			return nil, err
		}
		if id > 0 {
			ids = append(ids, id)
		}
	}
	return ids, rows.Err()
}

func (r *Repo) LoadCreds(ctx context.Context, userID int, credentialKey, jwtSecret, appEnv string) (tradeexec.Creds, error) {
	var appKey, secret, token, region sql.NullString
	err := r.DB.QueryRowContext(ctx, `
SELECT app_key, app_secret, access_token, region
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &secret, &token, &region)
	if err == sql.ErrNoRows {
		return tradeexec.Creds{UserID: userID, Source: "none"}, nil
	}
	if err != nil {
		return tradeexec.Creds{}, err
	}
	return tradeexec.Creds{
		UserID:      userID,
		AppKey:      strings.TrimSpace(appKey.String),
		AppSecret:   tradeexec.DecryptOrRaw(secret.String, credentialKey, jwtSecret, appEnv),
		AccessToken: tradeexec.DecryptOrRaw(token.String, credentialKey, jwtSecret, appEnv),
		Region:      strings.TrimSpace(region.String),
		Source:      "db",
	}, nil
}

func (r *Repo) LoadSettings(ctx context.Context, userID int) tradeexec.UserSettings {
	var appKey, token, enabled sql.NullString
	var ratio, pct sql.NullFloat64
	err := r.DB.QueryRowContext(ctx, `
SELECT app_key, access_token, auto_trade_enabled, daily_buy_ratio, max_symbol_position_pct
FROM quant_longbridge_config WHERE user_id = ?`, userID).Scan(&appKey, &token, &enabled, &ratio, &pct)
	s := tradeexec.UserSettings{
		UserID:               userID,
		DailyBuyRatio:        tradeexec.ClampDailyBuyRatio(tradeexec.DailyBuyPositionRatio),
		MaxSymbolPositionPct: tradeexec.DefaultMaxSymbolPositionPct,
	}
	if err != nil {
		return s
	}
	s.HasKeys = strings.TrimSpace(appKey.String) != "" && strings.TrimSpace(token.String) != ""
	s.AutoTradeEnabled = s.HasKeys && strings.TrimSpace(enabled.String) == "1"
	if ratio.Valid {
		s.DailyBuyRatio = tradeexec.ClampDailyBuyRatio(ratio.Float64)
	}
	if pct.Valid {
		s.MaxSymbolPositionPct = tradeexec.ClampMaxSymbolPositionPct(pct.Float64)
	}
	return s
}

func (r *Repo) BoundProfile(ctx context.Context, userID int, override string) string {
	raw := strings.ToLower(strings.TrimSpace(override))
	if raw == "conservative" || raw == "balanced" || raw == "aggressive" {
		return raw
	}
	var code sql.NullString
	_ = r.DB.QueryRowContext(ctx, `SELECT profile_code FROM plat_user_strategy_bind WHERE user_id = ?`, userID).Scan(&code)
	out := strings.ToLower(strings.TrimSpace(code.String))
	if out == "conservative" || out == "balanced" || out == "aggressive" {
		return out
	}
	return "balanced"
}

func (r *Repo) EnabledWatchlist(ctx context.Context, userID int) ([]Target, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT symbol, IFNULL(market,'US'), IFNULL(name,'')
FROM market_watchlist WHERE enabled = '1' AND user_id = ?
ORDER BY sort_order, create_time DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Target
	for rows.Next() {
		var t Target
		if err := rows.Scan(&t.Symbol, &t.Market, &t.Name); err != nil {
			return nil, err
		}
		t.Market = strings.ToUpper(t.Market)
		out = append(out, t)
	}
	return out, rows.Err()
}

func (r *Repo) HeatUniverse(ctx context.Context) ([]Target, error) {
	var out []Target
	seen := map[string]struct{}{}
	for _, market := range []string{"US", "HK"} {
		var tradeDate string
		err := r.DB.QueryRowContext(ctx, `
SELECT trade_date FROM market_heat_daily WHERE market = ? ORDER BY trade_date DESC LIMIT 1`, market).Scan(&tradeDate)
		if err != nil {
			continue
		}
		rows, err := r.DB.QueryContext(ctx, `
SELECT symbol FROM market_top50_snapshot WHERE market = ? AND trade_date = ? ORDER BY rank_no`, market, tradeDate)
		if err != nil {
			continue
		}
		for rows.Next() {
			var symbol string
			if err := rows.Scan(&symbol); err != nil {
				_ = rows.Close()
				return nil, err
			}
			if !tradeexec.IsAutoTradeMarket(market, symbol) {
				continue
			}
			code, mkt := tradeexec.ParseSymbolMarket(symbol, market)
			key := strings.ToUpper(code) + "|" + mkt
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			out = append(out, Target{Symbol: code, Market: mkt})
		}
		_ = rows.Close()
	}
	return out, nil
}

func (r *Repo) TodayStats(ctx context.Context, userID int) (int, float64, error) {
	today := time.Now().Format("2006-01-02")
	var count sql.NullInt64
	var notional sql.NullFloat64
	err := r.DB.QueryRowContext(ctx, `
SELECT COUNT(*), COALESCE(SUM(quantity * price), 0)
FROM plat_auto_trade_decision
WHERE user_id = ? AND create_time >= ? AND status IN ('submitted','filled')`, userID, today).Scan(&count, &notional)
	if err != nil {
		return 0, 0, err
	}
	return int(count.Int64), notional.Float64, nil
}

func (r *Repo) TodayBought(ctx context.Context, userID int) (map[string]struct{}, error) {
	today := time.Now().Format("2006-01-02")
	rows, err := r.DB.QueryContext(ctx, `
SELECT symbol FROM plat_auto_trade_decision
WHERE user_id = ? AND create_time >= ? AND side = 'BUY' AND status IN ('submitted','filled','pending')`, userID, today)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := map[string]struct{}{}
	for rows.Next() {
		var raw string
		if err := rows.Scan(&raw); err != nil {
			return nil, err
		}
		code, _ := tradeexec.ParseSymbolMarket(raw, "US")
		if code != "" {
			out[code] = struct{}{}
		}
	}
	return out, rows.Err()
}

func (r *Repo) InsertDecision(ctx context.Context, d DecisionRow) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_auto_trade_decision
(cycle_id, user_id, symbol, market, side, quantity, price, confidence, status, reason, source, order_id, error, create_time)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())`,
		d.CycleID, d.UserID, d.Symbol, d.Market, d.Side, d.Quantity, nullFloat(d.Price),
		nullInt(d.Confidence), d.Status, nullStr(d.Reason), d.Source, nullStr(d.OrderID), nullStr(d.Error))
	return err
}

func (r *Repo) InsertRiskEvent(ctx context.Context, userID int, level, title, content, symbol, review, handled string) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_risk_event
(user_id, event_level, title, content, symbol, handled, review_status, create_time)
VALUES (?,?,?,?,?,?,?,NOW())`, userID, level, title, content, symbol, handled, review)
	return err
}

func (r *Repo) HasPendingRisk(ctx context.Context, userID int, symbol string) (bool, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT symbol, review_status FROM plat_risk_event
WHERE user_id = ? ORDER BY create_time DESC LIMIT 80`, userID)
	if err != nil {
		return false, err
	}
	defer rows.Close()
	for rows.Next() {
		var sym, status string
		if err := rows.Scan(&sym, &status); err != nil {
			return false, err
		}
		if sym == symbol && (status == "pending_review" || status == "need_review" || status == "overdue") {
			return true, nil
		}
	}
	return false, rows.Err()
}

func (r *Repo) InsertRunLog(ctx context.Context, row RunLog) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_ai_trade_run_log
(cycle_id, user_id, source, strategy_profile, target_count, evaluated_count, opportunity_count,
 submitted_orders_count, status, guardrail_snapshot, candidates_snapshot, opportunities_snapshot,
 skipped_reasons, message, started_at, finished_at, create_time)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())`,
		row.CycleID, row.UserID, row.Source, row.Profile, row.TargetCount, row.EvaluatedCount,
		row.OpportunityCount, row.Submitted, row.Status, row.GuardrailJSON, row.CandidatesJSON,
		row.OpportunitiesJSON, row.SkippedJSON, row.Message, row.Started, row.Finished)
	return err
}

func (r *Repo) InsertReadmodel(ctx context.Context, kind string, payload interface{}) error {
	raw, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	_, err = r.DB.ExecContext(ctx, `
INSERT INTO quant_readmodel_snapshot (snapshot_type, payload_json, create_time)
VALUES (?, ?, NOW())`, kind, string(raw))
	return err
}

func (r *Repo) ListQueuedItems(ctx context.Context) ([]DailyItem, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT item_id, list_id, user_id, trade_date, symbol, IFNULL(market,'US'), IFNULL(status,''),
       IFNULL(side,'BUY'), IFNULL(quantity,0), IFNULL(price,0), IFNULL(order_id,''), IFNULL(error,'')
FROM quant_daily_list_item WHERE status = 'queued'`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []DailyItem
	for rows.Next() {
		var it DailyItem
		var tradeDate time.Time
		if err := rows.Scan(&it.ItemID, &it.ListID, &it.UserID, &tradeDate, &it.Symbol, &it.Market, &it.Status,
			&it.Side, &it.Quantity, &it.Price, &it.OrderID, &it.Error); err != nil {
			return nil, err
		}
		it.TradeDate = tradeDate.Format("2006-01-02")
		it.Market = strings.ToUpper(it.Market)
		out = append(out, it)
	}
	return out, rows.Err()
}

func (r *Repo) UpdateDailyItem(ctx context.Context, it DailyItem) error {
	if r == nil || r.DB == nil {
		return nil
	}
	_, err := r.DB.ExecContext(ctx, `
UPDATE quant_daily_list_item
SET status=?, quantity=?, order_id=?, error=?, update_time=NOW()
WHERE item_id=?`, it.Status, it.Quantity, nullStr(it.OrderID), nullStr(it.Error), it.ItemID)
	return err
}

func (r *Repo) UpsertDailyList(ctx context.Context, userID int, scanDate, tradeDate, profile, status, message string, itemCount int) (int64, error) {
	var listID sql.NullInt64
	_ = r.DB.QueryRowContext(ctx, `
SELECT list_id FROM quant_daily_list WHERE user_id = ? AND trade_date = ?`, userID, tradeDate).Scan(&listID)
	if listID.Valid {
		_, err := r.DB.ExecContext(ctx, `
UPDATE quant_daily_list SET scan_date=?, profile=?, status=?, item_count=?, message=?, update_time=NOW()
WHERE list_id=?`, scanDate, profile, status, itemCount, message, listID.Int64)
		return listID.Int64, err
	}
	res, err := r.DB.ExecContext(ctx, `
INSERT INTO quant_daily_list (user_id, scan_date, trade_date, profile, status, item_count, message, create_time, update_time)
VALUES (?,?,?,?,?,?,?,NOW(),NOW())`, userID, scanDate, tradeDate, profile, status, itemCount, message)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (r *Repo) ReplaceDailyItems(ctx context.Context, listID int64, items []DailyItem) error {
	if _, err := r.DB.ExecContext(ctx, `DELETE FROM quant_daily_list_item WHERE list_id = ?`, listID); err != nil {
		return err
	}
	for _, it := range items {
		if _, err := r.DB.ExecContext(ctx, `
INSERT INTO quant_daily_list_item
(list_id, user_id, trade_date, symbol, market, name, signal, score, confidence, reason,
 selected, auto_trade, status, side, quantity, price, create_time, update_time)
VALUES (?,?,?,?,?,?,?,?,?,?, '0','0',?,?,?,?,NOW(),NOW())`,
			listID, it.UserID, it.TradeDate, it.Symbol, it.Market, nullStr(it.Name), it.Signal,
			it.Score, it.Confidence, truncate(it.Reason, 500), it.Status, it.Side, it.Quantity, it.Price); err != nil {
			return err
		}
	}
	return nil
}

func (r *Repo) LatestKlineClose(ctx context.Context, query func(ctx context.Context, market string, symbols []string) (map[string]float64, error), market, symbol string) (float64, error) {
	if query == nil {
		return 0, fmt.Errorf("no kline reader")
	}
	m, err := query(ctx, market, []string{symbol})
	if err != nil {
		return 0, err
	}
	return m[symbol], nil
}

type Target struct {
	Symbol string
	Market string
	Name   string
}

type DecisionRow struct {
	CycleID    string
	UserID     int
	Symbol     string
	Market     string
	Side       string
	Quantity   int
	Price      float64
	Confidence int
	Status     string
	Reason     string
	Source     string
	OrderID    string
	Error      string
}

type RunLog struct {
	CycleID            string
	UserID             int
	Source             string
	Profile            string
	TargetCount        int
	EvaluatedCount     int
	OpportunityCount   int
	Submitted          int
	Status             string
	GuardrailJSON      string
	CandidatesJSON     string
	OpportunitiesJSON  string
	SkippedJSON        string
	Message            string
	Started            time.Time
	Finished           time.Time
}

type DailyItem struct {
	ItemID     int64
	ListID     int64
	UserID     int
	TradeDate  string
	Symbol     string
	Market     string
	Name       string
	Signal     string
	Score      float64
	Confidence int
	Reason     string
	Status     string
	Side       string
	Quantity   int
	Price      float64
	OrderID    string
	Error      string
}

func nullStr(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}

func nullFloat(v float64) interface{} {
	if v == 0 {
		return nil
	}
	return v
}

func nullInt(v int) interface{} {
	if v == 0 {
		return nil
	}
	return v
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func mustJSON(v interface{}) string {
	raw, _ := json.Marshal(v)
	return string(raw)
}
