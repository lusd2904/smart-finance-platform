package platform

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
)

type Repo struct {
	DB *sql.DB
}

type Notification struct {
	ID         int
	Title      string
	Content    string
	Level      string
	Category   string
	Read       bool
	CreateTime string
}

type BacktestRun struct {
	ID           int
	Symbol       string
	Market       string
	Days         int
	Strategy     string
	Trades       int
	ReturnPct    float64
	FinalEquity  float64
	MaxDrawdown  float64
	WinRate      float64
	EquityCurve  string
	Message      string
	CreateTime   string
}

type RiskRule struct {
	ID         int
	Name       string
	Type       string
	Symbol     string
	Threshold  float64
	Enabled    string
	Remark     string
	CreateTime string
}

type RiskEvent struct {
	ID           int
	RuleID       sql.NullInt64
	Level        string
	Title        string
	Content      string
	Symbol       string
	Handled      string
	ReviewStatus string
	HandleRemark sql.NullString
	HandledBy    sql.NullString
	HandleTime   sql.NullTime
	CreateTime   time.Time
}

type StrategyProfile struct {
	Code       string
	Name       string
	ConfigJSON string
	UpdateTime sql.NullTime
}

type AiBatchRun struct {
	ID           int
	CycleID      string
	SymbolsCount int
	SuccessCount int
	Status       string
	Summary      string
	CreateTime   string
}

type AiBatchItem struct {
	ID         int
	Symbol     string
	Market     string
	Decision   sql.NullString
	Confidence sql.NullInt64
	Summary    sql.NullString
	Status     string
	CreateTime string
}

type AiTradeRunLog struct {
	RunID                int
	CycleID              string
	UserID               int
	Source               string
	StrategyProfile      string
	TargetCount          int
	EvaluatedCount       int
	OpportunityCount     int
	SubmittedOrdersCount int
	Status               string
	GuardrailSnapshot    string
	CandidatesSnapshot   string
	OpportunitiesSnapshot string
	SkippedReasons       string
	Message              string
	StartedAt            sql.NullTime
	FinishedAt           sql.NullTime
}

type AutoDecision struct {
	DecisionID int
	CycleID    string
	Symbol     string
	Market     string
	Side       string
	Quantity   int
	Price      sql.NullFloat64
	Confidence sql.NullInt64
	Status     string
	Reason     sql.NullString
	Source     string
	OrderID    sql.NullString
	Error      sql.NullString
	CreateTime string
}

type FeishuSub struct {
	SubID             int
	UserID            int
	PersonalEnabled   string
	GroupEnabled      string
	PersonalWebhook   sql.NullString
	GroupWebhook      sql.NullString
	PushTime          string
	Timezone          string
	LastPersonalKey   sql.NullString
	LastGroupKey      sql.NullString
	LastError         sql.NullString
}

type Target struct {
	Symbol string
	Market string
	Name   string
}

type CoverageInstrument struct {
	Symbol   string
	Name     string
	Market   string
	Category string
}

type StrategySignal struct {
	UserID     int
	Symbol     string
	Score      float64
	Signal     string
}

func (r *Repo) ListNotifications(ctx context.Context, userID, limit int) ([]Notification, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT notice_id, title, content, level, category, is_read, create_time
FROM plat_notification WHERE user_id = ? ORDER BY create_time DESC LIMIT ?`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Notification
	for rows.Next() {
		var n Notification
		var read string
		var ct sql.NullTime
		if err := rows.Scan(&n.ID, &n.Title, &n.Content, &n.Level, &n.Category, &read, &ct); err != nil {
			return nil, err
		}
		n.Read = read == "1"
		n.CreateTime = formatTime(ct)
		out = append(out, n)
	}
	return out, rows.Err()
}

func (r *Repo) MarkNotificationsRead(ctx context.Context, userID int, noticeID *int) (int, error) {
	if noticeID != nil {
		res, err := r.DB.ExecContext(ctx, `
UPDATE plat_notification SET is_read = '1'
WHERE notice_id = ? AND user_id = ?`, *noticeID, userID)
		if err != nil {
			return 0, err
		}
		n, _ := res.RowsAffected()
		return int(n), nil
	}
	res, err := r.DB.ExecContext(ctx, `
UPDATE plat_notification SET is_read = '1'
WHERE user_id = ? AND is_read = '0'`, userID)
	if err != nil {
		return 0, err
	}
	n, _ := res.RowsAffected()
	return int(n), nil
}

func (r *Repo) AddNotification(ctx context.Context, userID int, title, content, level, category string) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_notification (user_id, title, content, level, category, is_read, create_time)
VALUES (?, ?, ?, ?, ?, '0', NOW())`, userID, title, content, level, category)
	return err
}

func (r *Repo) AddBacktestRun(ctx context.Context, userID int, item map[string]interface{}) (int64, error) {
	res, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_backtest_run
(user_id, symbol, market, days, strategy, trades, return_pct, final_equity, max_drawdown, win_rate, equity_curve_json, message, create_time)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NOW())`,
		userID, item["symbol"], item["market"], item["days"], item["strategy"],
		item["trades"], item["return_pct"], item["final_equity"], item["max_drawdown"],
		item["win_rate"], item["equity_curve_json"], item["message"])
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (r *Repo) ListBacktests(ctx context.Context, userID, limit int) ([]BacktestRun, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT run_id, symbol, market, days, strategy, trades, return_pct, final_equity, max_drawdown, win_rate, message, create_time
FROM plat_backtest_run WHERE user_id = ? ORDER BY create_time DESC LIMIT ?`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []BacktestRun
	for rows.Next() {
		var b BacktestRun
		var ct sql.NullTime
		if err := rows.Scan(&b.ID, &b.Symbol, &b.Market, &b.Days, &b.Strategy, &b.Trades,
			&b.ReturnPct, &b.FinalEquity, &b.MaxDrawdown, &b.WinRate, &b.Message, &ct); err != nil {
			return nil, err
		}
		b.CreateTime = formatTime(ct)
		out = append(out, b)
	}
	return out, rows.Err()
}

func (r *Repo) GetBacktest(ctx context.Context, userID, runID int) (*BacktestRun, error) {
	var b BacktestRun
	var ct sql.NullTime
	err := r.DB.QueryRowContext(ctx, `
SELECT run_id, symbol, market, days, strategy, trades, return_pct, final_equity, max_drawdown, win_rate, equity_curve_json, message, create_time
FROM plat_backtest_run WHERE run_id = ? AND user_id = ?`, runID, userID).Scan(
		&b.ID, &b.Symbol, &b.Market, &b.Days, &b.Strategy, &b.Trades,
		&b.ReturnPct, &b.FinalEquity, &b.MaxDrawdown, &b.WinRate, &b.EquityCurve, &b.Message, &ct)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	b.CreateTime = formatTime(ct)
	return &b, nil
}

func (r *Repo) ListRiskRules(ctx context.Context) ([]RiskRule, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT rule_id, rule_name, rule_type, IFNULL(symbol,''), threshold, enabled, IFNULL(remark,''), create_time
FROM plat_risk_rule ORDER BY rule_id DESC`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []RiskRule
	for rows.Next() {
		var rr RiskRule
		var ct sql.NullTime
		if err := rows.Scan(&rr.ID, &rr.Name, &rr.Type, &rr.Symbol, &rr.Threshold, &rr.Enabled, &rr.Remark, &ct); err != nil {
			return nil, err
		}
		rr.CreateTime = formatTime(ct)
		out = append(out, rr)
	}
	return out, rows.Err()
}

func (r *Repo) AddRiskRule(ctx context.Context, name, typ, symbol string, threshold float64, enabled, remark string) (int64, error) {
	res, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_risk_rule (rule_name, rule_type, symbol, threshold, enabled, remark, create_time, update_time)
VALUES (?,?,?,?,?,?,NOW(),NOW())`, name, typ, nullStr(symbol), threshold, enabled, nullStr(remark))
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (r *Repo) UpdateRiskRule(ctx context.Context, id int, name, typ, symbol string, threshold float64, enabled, remark string) error {
	_, err := r.DB.ExecContext(ctx, `
UPDATE plat_risk_rule SET rule_name=?, rule_type=?, symbol=?, threshold=?, enabled=?, remark=?, update_time=NOW()
WHERE rule_id=?`, name, typ, nullStr(symbol), threshold, enabled, nullStr(remark), id)
	return err
}

func (r *Repo) DeleteRiskRule(ctx context.Context, id int) error {
	_, err := r.DB.ExecContext(ctx, `DELETE FROM plat_risk_rule WHERE rule_id = ?`, id)
	return err
}

func (r *Repo) ExpireOverdueRiskEvents(ctx context.Context, userID int, hours int) (int, error) {
	res, err := r.DB.ExecContext(ctx, `
UPDATE plat_risk_event SET review_status = 'overdue'
WHERE user_id = ? AND review_status IN ('pending_review','need_review')
  AND create_time <= DATE_SUB(NOW(), INTERVAL ? HOUR)`, userID, hours)
	if err != nil {
		return 0, err
	}
	n, _ := res.RowsAffected()
	return int(n), nil
}

func (r *Repo) ListRiskEvents(ctx context.Context, userID, limit int, status string) ([]RiskEvent, error) {
	q := `
SELECT event_id, rule_id, event_level, title, content, IFNULL(symbol,''), handled, review_status,
       handle_remark, handled_by, handle_time, create_time
FROM plat_risk_event WHERE user_id = ?`
	args := []interface{}{userID}
	if status != "" {
		q += ` AND review_status = ?`
		args = append(args, status)
	}
	q += ` ORDER BY create_time DESC LIMIT ?`
	args = append(args, limit)
	rows, err := r.DB.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []RiskEvent
	for rows.Next() {
		var e RiskEvent
		if err := rows.Scan(&e.ID, &e.RuleID, &e.Level, &e.Title, &e.Content, &e.Symbol,
			&e.Handled, &e.ReviewStatus, &e.HandleRemark, &e.HandledBy, &e.HandleTime, &e.CreateTime); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

func (r *Repo) GetRiskEvent(ctx context.Context, userID, eventID int) (*RiskEvent, error) {
	var e RiskEvent
	err := r.DB.QueryRowContext(ctx, `
SELECT event_id, rule_id, event_level, title, content, IFNULL(symbol,''), handled, review_status,
       handle_remark, handled_by, handle_time, create_time
FROM plat_risk_event WHERE event_id = ? AND user_id = ?`, eventID, userID).Scan(
		&e.ID, &e.RuleID, &e.Level, &e.Title, &e.Content, &e.Symbol,
		&e.Handled, &e.ReviewStatus, &e.HandleRemark, &e.HandledBy, &e.HandleTime, &e.CreateTime)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &e, nil
}

func (r *Repo) AddRiskEvent(ctx context.Context, userID int, ruleID *int, level, title, content, symbol, review, handled string) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_risk_event (user_id, rule_id, event_level, title, content, symbol, handled, review_status, create_time)
VALUES (?,?,?,?,?,?,?,?,NOW())`, userID, nullIntPtr(ruleID), level, title, content, nullStr(symbol), handled, review)
	return err
}

func (r *Repo) UpdateRiskEventStatus(ctx context.Context, userID, eventID int, handled, review, remark, operator string, handleTime time.Time) (bool, error) {
	res, err := r.DB.ExecContext(ctx, `
UPDATE plat_risk_event SET handled=?, review_status=?, handle_remark=?, handled_by=?, handle_time=?
WHERE event_id=? AND user_id=?`, handled, review, nullStr(remark), nullStr(operator), handleTime, eventID, userID)
	if err != nil {
		return false, err
	}
	n, _ := res.RowsAffected()
	return n > 0, nil
}

func (r *Repo) ListStrategyProfiles(ctx context.Context) ([]StrategyProfile, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT profile_code, profile_name, config_json, update_time FROM plat_strategy_profile ORDER BY profile_code`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []StrategyProfile
	for rows.Next() {
		var p StrategyProfile
		if err := rows.Scan(&p.Code, &p.Name, &p.ConfigJSON, &p.UpdateTime); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (r *Repo) GetUserStrategyProfile(ctx context.Context, userID int, code string) (*StrategyProfile, error) {
	var p StrategyProfile
	err := r.DB.QueryRowContext(ctx, `
SELECT profile_code, profile_name, config_json, update_time
FROM plat_strategy_profile_user WHERE user_id = ? AND profile_code = ?`, userID, code).Scan(
		&p.Code, &p.Name, &p.ConfigJSON, &p.UpdateTime)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &p, nil
}

func (r *Repo) ListUserStrategyProfiles(ctx context.Context, userID int) ([]StrategyProfile, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT profile_code, profile_name, config_json, update_time
FROM plat_strategy_profile_user WHERE user_id = ? ORDER BY profile_code`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []StrategyProfile
	for rows.Next() {
		var p StrategyProfile
		if err := rows.Scan(&p.Code, &p.Name, &p.ConfigJSON, &p.UpdateTime); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

func (r *Repo) UpsertUserStrategyProfile(ctx context.Context, userID int, code, name, configJSON string) error {
	var id sql.NullInt64
	_ = r.DB.QueryRowContext(ctx, `
SELECT id FROM plat_strategy_profile_user WHERE user_id = ? AND profile_code = ?`, userID, code).Scan(&id)
	if id.Valid {
		_, err := r.DB.ExecContext(ctx, `
UPDATE plat_strategy_profile_user SET profile_name=?, config_json=?, update_time=NOW()
WHERE user_id=? AND profile_code=?`, name, configJSON, userID, code)
		return err
	}
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_strategy_profile_user (user_id, profile_code, profile_name, config_json, update_time)
VALUES (?,?,?,?,NOW())`, userID, code, name, configJSON)
	return err
}

func (r *Repo) UpsertGlobalStrategyProfile(ctx context.Context, code, name, configJSON string) error {
	var id sql.NullInt64
	_ = r.DB.QueryRowContext(ctx, `SELECT profile_id FROM plat_strategy_profile WHERE profile_code = ?`, code).Scan(&id)
	if id.Valid {
		_, err := r.DB.ExecContext(ctx, `
UPDATE plat_strategy_profile SET profile_name=?, config_json=?, update_time=NOW() WHERE profile_code=?`,
			name, configJSON, code)
		return err
	}
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_strategy_profile (profile_code, profile_name, config_json, update_time)
VALUES (?,?,?,NOW())`, code, name, configJSON)
	return err
}

func (r *Repo) GetBoundProfile(ctx context.Context, userID int) string {
	var code sql.NullString
	_ = r.DB.QueryRowContext(ctx, `SELECT profile_code FROM plat_user_strategy_bind WHERE user_id = ?`, userID).Scan(&code)
	out := strings.ToLower(strings.TrimSpace(code.String))
	if out == "conservative" || out == "balanced" || out == "aggressive" {
		return out
	}
	return "balanced"
}

func (r *Repo) BindUserStrategy(ctx context.Context, userID int, code string) error {
	var id sql.NullInt64
	_ = r.DB.QueryRowContext(ctx, `SELECT bind_id FROM plat_user_strategy_bind WHERE user_id = ?`, userID).Scan(&id)
	if id.Valid {
		_, err := r.DB.ExecContext(ctx, `
UPDATE plat_user_strategy_bind SET profile_code=?, update_time=NOW() WHERE user_id=?`, code, userID)
		return err
	}
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_user_strategy_bind (user_id, profile_code, update_time) VALUES (?,?,NOW())`, userID, code)
	return err
}

func (r *Repo) AddAiBatchRun(ctx context.Context, cycleID string, symbolsCount int, summary string) (int64, error) {
	res, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_ai_batch_run (cycle_id, symbols_count, success_count, status, summary, create_time)
VALUES (?, ?, 0, '0', ?, NOW())`, cycleID, symbolsCount, summary)
	if err != nil {
		return 0, err
	}
	return res.LastInsertId()
}

func (r *Repo) ListAiBatches(ctx context.Context, limit int) ([]AiBatchRun, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT batch_id, cycle_id, symbols_count, success_count, status, summary, create_time
FROM plat_ai_batch_run ORDER BY create_time DESC LIMIT ?`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []AiBatchRun
	for rows.Next() {
		var b AiBatchRun
		var ct sql.NullTime
		if err := rows.Scan(&b.ID, &b.CycleID, &b.SymbolsCount, &b.SuccessCount, &b.Status, &b.Summary, &ct); err != nil {
			return nil, err
		}
		b.CreateTime = formatTime(ct)
		out = append(out, b)
	}
	return out, rows.Err()
}

func (r *Repo) ListAiBatchItems(ctx context.Context, batchID int) ([]AiBatchItem, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT item_id, symbol, market, decision, confidence, summary, status, create_time
FROM plat_ai_batch_item WHERE batch_id = ? ORDER BY item_id`, batchID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []AiBatchItem
	for rows.Next() {
		var it AiBatchItem
		var ct sql.NullTime
		if err := rows.Scan(&it.ID, &it.Symbol, &it.Market, &it.Decision, &it.Confidence, &it.Summary, &it.Status, &ct); err != nil {
			return nil, err
		}
		it.CreateTime = formatTime(ct)
		out = append(out, it)
	}
	return out, rows.Err()
}

func (r *Repo) ListAiTradeRuns(ctx context.Context, userID, limit int) ([]AiTradeRunLog, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT run_id, cycle_id, user_id, source, strategy_profile, target_count, evaluated_count,
       opportunity_count, submitted_orders_count, status, guardrail_snapshot, candidates_snapshot,
       opportunities_snapshot, skipped_reasons, message, started_at, finished_at
FROM plat_ai_trade_run_log WHERE user_id = ? ORDER BY run_id DESC LIMIT ?`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []AiTradeRunLog
	for rows.Next() {
		var l AiTradeRunLog
		if err := rows.Scan(&l.RunID, &l.CycleID, &l.UserID, &l.Source, &l.StrategyProfile,
			&l.TargetCount, &l.EvaluatedCount, &l.OpportunityCount, &l.SubmittedOrdersCount, &l.Status,
			&l.GuardrailSnapshot, &l.CandidatesSnapshot, &l.OpportunitiesSnapshot, &l.SkippedReasons,
			&l.Message, &l.StartedAt, &l.FinishedAt); err != nil {
			return nil, err
		}
		out = append(out, l)
	}
	return out, rows.Err()
}

func (r *Repo) ListAutoDecisions(ctx context.Context, limit int, cycleID string) ([]AutoDecision, error) {
	q := `
SELECT decision_id, cycle_id, symbol, market, side, quantity, price, confidence, status, reason, source, order_id, error, create_time
FROM plat_auto_trade_decision`
	args := []interface{}{}
	if cycleID != "" {
		q += ` WHERE cycle_id = ?`
		args = append(args, cycleID)
	}
	q += ` ORDER BY decision_id DESC LIMIT ?`
	args = append(args, limit)
	rows, err := r.DB.QueryContext(ctx, q, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []AutoDecision
	for rows.Next() {
		var d AutoDecision
		var ct sql.NullTime
		if err := rows.Scan(&d.DecisionID, &d.CycleID, &d.Symbol, &d.Market, &d.Side, &d.Quantity,
			&d.Price, &d.Confidence, &d.Status, &d.Reason, &d.Source, &d.OrderID, &d.Error, &ct); err != nil {
			return nil, err
		}
		d.CreateTime = formatTime(ct)
		out = append(out, d)
	}
	return out, rows.Err()
}

func (r *Repo) GetFeishuSub(ctx context.Context, userID int) (*FeishuSub, error) {
	var f FeishuSub
	err := r.DB.QueryRowContext(ctx, `
SELECT sub_id, user_id, personal_enabled, group_enabled, personal_webhook, group_webhook,
       push_time, timezone, last_personal_key, last_group_key, last_error
FROM plat_feishu_subscription WHERE user_id = ?`, userID).Scan(
		&f.SubID, &f.UserID, &f.PersonalEnabled, &f.GroupEnabled, &f.PersonalWebhook, &f.GroupWebhook,
		&f.PushTime, &f.Timezone, &f.LastPersonalKey, &f.LastGroupKey, &f.LastError)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return &f, nil
}

func (r *Repo) UpsertFeishuSub(ctx context.Context, userID int, personal, group, personalWH, groupWH, pushTime, tz string) (*FeishuSub, error) {
	existing, _ := r.GetFeishuSub(ctx, userID)
	if existing != nil {
		_, err := r.DB.ExecContext(ctx, `
UPDATE plat_feishu_subscription SET personal_enabled=?, group_enabled=?, personal_webhook=?, group_webhook=?,
       push_time=?, timezone=?, update_time=NOW() WHERE user_id=?`,
			personal, group, nullStr(personalWH), nullStr(groupWH), pushTime, tz, userID)
		if err != nil {
			return nil, err
		}
		return r.GetFeishuSub(ctx, userID)
	}
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_feishu_subscription
(user_id, personal_enabled, group_enabled, personal_webhook, group_webhook, push_time, timezone, create_time, update_time)
VALUES (?,?,?,?,?,?,?,NOW(),NOW())`, userID, personal, group, nullStr(personalWH), nullStr(groupWH), pushTime, tz)
	if err != nil {
		return nil, err
	}
	return r.GetFeishuSub(ctx, userID)
}

func (r *Repo) ListCoverageInstruments(ctx context.Context) ([]CoverageInstrument, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT symbol, IFNULL(name,''), market, IFNULL(category,'')
FROM market_instrument WHERE enabled = '1' AND category != 'listed'
ORDER BY market, symbol`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []CoverageInstrument
	for rows.Next() {
		var c CoverageInstrument
		if err := rows.Scan(&c.Symbol, &c.Name, &c.Market, &c.Category); err != nil {
			return nil, err
		}
		out = append(out, c)
	}
	return out, rows.Err()
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

func (r *Repo) InsertDecision(ctx context.Context, userID int, cycleID, symbol, market, side string, qty int, price float64, confidence int, status, reason, source, orderID, errText string) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_auto_trade_decision
(cycle_id, user_id, symbol, market, side, quantity, price, confidence, status, reason, source, order_id, error, create_time)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())`,
		cycleID, userID, symbol, market, side, qty, nullFloat(price), nullInt(confidence),
		status, nullStr(reason), source, nullStr(orderID), nullStr(errText))
	return err
}

func (r *Repo) InsertRunLog(ctx context.Context, userID int, row map[string]interface{}) error {
	_, err := r.DB.ExecContext(ctx, `
INSERT INTO plat_ai_trade_run_log
(cycle_id, user_id, source, strategy_profile, target_count, evaluated_count, opportunity_count,
 submitted_orders_count, status, guardrail_snapshot, candidates_snapshot, opportunities_snapshot,
 skipped_reasons, message, started_at, finished_at, create_time)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NOW())`,
		row["cycle_id"], userID, row["source"], row["strategy_profile"], row["target_count"],
		row["evaluated_count"], row["opportunity_count"], row["submitted_orders_count"], row["status"],
		row["guardrail_snapshot"], row["candidates_snapshot"], row["opportunities_snapshot"],
		row["skipped_reasons"], row["message"], row["started_at"], row["finished_at"])
	return err
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

func (r *Repo) BoundProfile(ctx context.Context, userID int, override string) string {
	raw := strings.ToLower(strings.TrimSpace(override))
	if raw == "conservative" || raw == "balanced" || raw == "aggressive" {
		return raw
	}
	return r.GetBoundProfile(ctx, userID)
}

func (r *Repo) ListRecentStrategySignals(ctx context.Context, userID, limit int) ([]StrategySignal, error) {
	rows, err := r.DB.QueryContext(ctx, `
SELECT user_id, symbol, score, signal FROM quant_strategy_signal
WHERE user_id = ? ORDER BY create_time DESC LIMIT ?`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []StrategySignal
	for rows.Next() {
		var s StrategySignal
		if err := rows.Scan(&s.UserID, &s.Symbol, &s.Score, &s.Signal); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

func (r *Repo) EnsureSeedProfiles(ctx context.Context) error {
	seeds := map[string]map[string]interface{}{
		"conservative": {"name": "保守", "buyThreshold": 72, "sellThreshold": 42},
		"balanced":     {"name": "均衡", "buyThreshold": 64, "sellThreshold": 38},
		"aggressive":   {"name": "进取", "buyThreshold": 56, "sellThreshold": 32},
	}
	for code, cfg := range seeds {
		var id sql.NullInt64
		_ = r.DB.QueryRowContext(ctx, `SELECT profile_id FROM plat_strategy_profile WHERE profile_code = ?`, code).Scan(&id)
		if id.Valid {
			continue
		}
		raw, _ := json.Marshal(cfg)
		if err := r.UpsertGlobalStrategyProfile(ctx, code, fmt.Sprint(cfg["name"]), string(raw)); err != nil {
			return err
		}
	}
	var count int
	_ = r.DB.QueryRowContext(ctx, `SELECT COUNT(*) FROM plat_risk_rule`).Scan(&count)
	if count == 0 {
		seeds := []struct {
			name, typ, remark string
			thr               float64
		}{
			{"单票仓位上限", "position", "单标的仓位不超过总资产20%", 20},
			{"单日亏损熔断", "loss", "当日浮亏超过5%触发熔断提示", 5},
			{"集中度限制", "concentration", "行业/主题集中度警戒线", 40},
		}
		for _, s := range seeds {
			if _, err := r.AddRiskRule(ctx, s.name, s.typ, "", s.thr, "1", s.remark); err != nil {
				return err
			}
		}
	}
	return nil
}

func formatTime(t sql.NullTime) string {
	if !t.Valid {
		return ""
	}
	return t.Time.Format("2006-01-02 15:04:05")
}

func nullStr(s string) interface{} {
	if strings.TrimSpace(s) == "" {
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

func nullIntPtr(v *int) interface{} {
	if v == nil {
		return nil
	}
	return *v
}
