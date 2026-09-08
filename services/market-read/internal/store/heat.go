package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/heat"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/timeutil"
)

type HeatStore struct {
	db *sql.DB
}

func NewHeatStore(cfg *config.Config) (*HeatStore, error) {
	db, err := sql.Open("mysql", cfg.MySQLDSN())
	if err != nil {
		return nil, err
	}
	db.SetMaxOpenConns(8)
	db.SetMaxIdleConns(4)
	db.SetConnMaxLifetime(30 * time.Minute)
	if err := db.Ping(); err != nil {
		return nil, err
	}
	return &HeatStore{db: db}, nil
}

func (s *HeatStore) Close() error { return s.db.Close() }

type HeatRow struct {
	Market         string
	TradeDate      string
	IndexSymbol    sql.NullString
	IndexName      sql.NullString
	IndexChangePct sql.NullFloat64
	TotalTurnover  sql.NullFloat64
	AdvanceCount   sql.NullInt64
	DeclineCount   sql.NullInt64
	FlatCount      sql.NullInt64
	HeatScore      sql.NullFloat64
	HeatSummary    sql.NullString
	Currency       sql.NullString
	FilterRule     sql.NullString
	WeightsJSON    sql.NullString
	AsOfTime       sql.NullTime
	Status         sql.NullString
	Message        sql.NullString
}

type Top50Row struct {
	RankNo     int
	Symbol     string
	Name       sql.NullString
	MarketCap  sql.NullFloat64
	Turnover   sql.NullFloat64
	ChangePct  sql.NullFloat64
	Last       sql.NullFloat64
	Currency   sql.NullString
	AsOfTime   sql.NullTime
}

func (s *HeatStore) GetHeat(ctx context.Context, market, tradeDate string) (*HeatRow, error) {
	row := &HeatRow{}
	err := s.db.QueryRowContext(ctx, `
SELECT market, trade_date, index_symbol, index_name, index_change_pct, total_turnover,
       advance_count, decline_count, flat_count, heat_score, heat_summary, currency,
       filter_rule, weights_json, as_of_time, status, message
FROM market_heat_daily WHERE market = ? AND trade_date = ?`,
		strings.ToUpper(market), tradeDate).Scan(
		&row.Market, &row.TradeDate, &row.IndexSymbol, &row.IndexName, &row.IndexChangePct,
		&row.TotalTurnover, &row.AdvanceCount, &row.DeclineCount, &row.FlatCount, &row.HeatScore,
		&row.HeatSummary, &row.Currency, &row.FilterRule, &row.WeightsJSON, &row.AsOfTime,
		&row.Status, &row.Message,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return row, err
}

func (s *HeatStore) GetLatestHeat(ctx context.Context, market string) (*HeatRow, error) {
	row := &HeatRow{}
	err := s.db.QueryRowContext(ctx, `
SELECT market, trade_date, index_symbol, index_name, index_change_pct, total_turnover,
       advance_count, decline_count, flat_count, heat_score, heat_summary, currency,
       filter_rule, weights_json, as_of_time, status, message
FROM market_heat_daily WHERE market = ? ORDER BY trade_date DESC LIMIT 1`,
		strings.ToUpper(market)).Scan(
		&row.Market, &row.TradeDate, &row.IndexSymbol, &row.IndexName, &row.IndexChangePct,
		&row.TotalTurnover, &row.AdvanceCount, &row.DeclineCount, &row.FlatCount, &row.HeatScore,
		&row.HeatSummary, &row.Currency, &row.FilterRule, &row.WeightsJSON, &row.AsOfTime,
		&row.Status, &row.Message,
	)
	if err == sql.ErrNoRows {
		return nil, nil
	}
	return row, err
}

func (s *HeatStore) ListHeatTrend(ctx context.Context, market string, limit int) ([]HeatRow, error) {
	if limit < 1 {
		limit = 5
	}
	if limit > 30 {
		limit = 30
	}
	rows, err := s.db.QueryContext(ctx, `
SELECT market, trade_date, index_symbol, index_name, index_change_pct, total_turnover,
       advance_count, decline_count, flat_count, heat_score, heat_summary, currency,
       filter_rule, weights_json, as_of_time, status, message
FROM market_heat_daily WHERE market = ? ORDER BY trade_date DESC LIMIT ?`,
		strings.ToUpper(market), limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]HeatRow, 0)
	for rows.Next() {
		row := HeatRow{}
		if err := rows.Scan(
			&row.Market, &row.TradeDate, &row.IndexSymbol, &row.IndexName, &row.IndexChangePct,
			&row.TotalTurnover, &row.AdvanceCount, &row.DeclineCount, &row.FlatCount, &row.HeatScore,
			&row.HeatSummary, &row.Currency, &row.FilterRule, &row.WeightsJSON, &row.AsOfTime,
			&row.Status, &row.Message,
		); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	// reverse to ascending
	for i, j := 0, len(out)-1; i < j; i, j = i+1, j-1 {
		out[i], out[j] = out[j], out[i]
	}
	return out, rows.Err()
}

func (s *HeatStore) ListTop50(ctx context.Context, market, tradeDate string) ([]Top50Row, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT rank_no, symbol, name, market_cap, turnover, change_pct, last, currency, as_of_time
FROM market_top50_snapshot WHERE market = ? AND trade_date = ? ORDER BY rank_no`,
		strings.ToUpper(market), tradeDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]Top50Row, 0)
	for rows.Next() {
		row := Top50Row{}
		if err := rows.Scan(&row.RankNo, &row.Symbol, &row.Name, &row.MarketCap, &row.Turnover,
			&row.ChangePct, &row.Last, &row.Currency, &row.AsOfTime); err != nil {
			return nil, err
		}
		out = append(out, row)
	}
	return out, rows.Err()
}

func (s *HeatStore) WatchlistSymbols(ctx context.Context, userID int64) (map[string]bool, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT symbol, market FROM market_watchlist WHERE user_id = ? AND enabled = '1'`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	set := make(map[string]bool)
	for rows.Next() {
		var symbol, market string
		if err := rows.Scan(&symbol, &market); err != nil {
			return nil, err
		}
		set[fmt.Sprintf("%s|%s", strings.ToUpper(symbol), strings.ToUpper(market))] = true
	}
	return set, rows.Err()
}

func SerializeHeat(row *HeatRow) map[string]interface{} {
	if row == nil {
		return nil
	}
	stale := false
	status := nullString(row.Status, "ok")
	if row.AsOfTime.Valid {
		if timeutil.NowBeijing().Sub(row.AsOfTime.Time) > 36*time.Hour && status == "ok" {
			stale = true
			status = "stale"
		}
	}
	weights := map[string]float64{}
	if row.WeightsJSON.Valid && row.WeightsJSON.String != "" {
		_ = json.Unmarshal([]byte(row.WeightsJSON.String), &weights)
	}
	staleHint := nilString("")
	if stale {
		staleHint = "数据可能不是最新收盘快照，请选择其他交易日或等待任务刷新。"
	}
	return map[string]interface{}{
		"market":         row.Market,
		"tradeDate":      row.TradeDate,
		"indexSymbol":    nullString(row.IndexSymbol, ""),
		"indexName":      nullString(row.IndexName, ""),
		"indexChangePct": nullFloat(row.IndexChangePct),
		"totalTurnover":  nullFloat(row.TotalTurnover),
		"advanceCount":   nullInt(row.AdvanceCount),
		"declineCount":   nullInt(row.DeclineCount),
		"flatCount":      nullInt(row.FlatCount),
		"heatScore":      nullFloat(row.HeatScore),
		"heatSummary":    nullString(row.HeatSummary, ""),
		"currency":       nullString(row.Currency, ""),
		"filterRule":     nullString(row.FilterRule, ""),
		"weights":        weights,
		"asOfTime":       formatTime(row.AsOfTime),
		"status":         status,
		"message":        nullString(row.Message, ""),
		"staleHint":      staleHint,
	}
}

func SerializeTop50(rows []Top50Row) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		out = append(out, map[string]interface{}{
			"rankNo":     row.RankNo,
			"symbol":     row.Symbol,
			"name":       nullString(row.Name, row.Symbol),
			"marketCap":  nullFloat(row.MarketCap),
			"turnover":   nullFloat(row.Turnover),
			"changePct":  nullFloat(row.ChangePct),
			"last":       nullFloat(row.Last),
			"currency":   nullString(row.Currency, ""),
			"asOfTime":   formatTime(row.AsOfTime),
		})
	}
	return out
}

func MarketMeta(market string) map[string]interface{} {
	meta := heat.MarketMeta[strings.ToUpper(market)]
	return map[string]interface{}{
		"label":         meta.Label,
		"currency":      meta.Currency,
		"capFilterRule": meta.CapRule,
	}
}

func nullString(v sql.NullString, fallback string) interface{} {
	if v.Valid {
		return v.String
	}
	if fallback == "" {
		return nil
	}
	return fallback
}

func nullFloat(v sql.NullFloat64) interface{} {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func nullInt(v sql.NullInt64) interface{} {
	if v.Valid {
		return v.Int64
	}
	return nil
}

func nilString(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}

func formatTime(v sql.NullTime) interface{} {
	if !v.Valid {
		return nil
	}
	return timeutil.FormatBeijing(v.Time)
}
