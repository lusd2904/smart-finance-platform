package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/heat"
)

func (s *Service) CollectMarketHeat(ctx context.Context, market, tradeDate string) (map[string]interface{}, error) {
	mkt, err := heat.NormalizeMarket(market)
	if err != nil {
		return nil, err
	}
	session := heat.ResolveTradeDate(mkt, tradeDate, time.Now())
	if !heat.IsWeekday(session) {
		return map[string]interface{}{"skipped": true, "market": mkt, "tradeDate": session, "reason": "non_trading_day"}, nil
	}
	weights := s.heatWeights(ctx)
	candidates, extras := heat.FetchPublicUniverse(mkt)
	if len(candidates) == 0 {
		existing, _ := s.countTop50(ctx, mkt, session)
		return map[string]interface{}{
			"skipped": true, "market": mkt, "tradeDate": session,
			"reason": "public_eod_empty", "keptExistingTop50": existing,
		}, nil
	}
	baseline := s.heatTurnoverBaseline(ctx, mkt)
	result := heat.BuildCollect(mkt, session, weights, candidates, extras, baseline)
	if result.Skipped {
		existing, _ := s.countTop50(ctx, mkt, session)
		return map[string]interface{}{
			"skipped": true, "market": mkt, "tradeDate": session,
			"reason": result.Reason, "candidateCount": result.CandidateCount,
			"keptExistingTop50": existing,
		}, nil
	}
	if err := s.persistHeat(ctx, result); err != nil {
		return nil, err
	}
	asOf := time.Now().In(beijingLoc())
	return map[string]interface{}{
		"market":         result.Market,
		"tradeDate":      result.TradeDate,
		"heatScore":      result.HeatScore,
		"top50Count":     len(result.Top50),
		"candidateCount": result.CandidateCount,
		"status":         result.Status,
		"source":         result.Sources,
		"asOfTime":       asOf.Format("2006-01-02 15:04:05"),
	}, nil
}

func (s *Service) heatWeights(ctx context.Context) map[string]float64 {
	weights := heat.DefaultWeights()
	if s.rdb == nil {
		return heat.NormalizeWeights(weights)
	}
	for key, field := range heat.WeightConfigKeys {
		raw, err := s.rdb.Get(ctx, "sys_config:"+key).Result()
		if err != nil || strings.TrimSpace(raw) == "" {
			continue
		}
		var v float64
		if _, err := fmt.Sscan(raw, &v); err == nil {
			weights[field] = v
		}
	}
	return heat.NormalizeWeights(weights)
}

func (s *Service) heatTurnoverBaseline(ctx context.Context, market string) *float64 {
	rows, err := s.db.QueryContext(ctx, `
SELECT total_turnover FROM market_heat_daily
WHERE market=? AND total_turnover IS NOT NULL AND total_turnover > 0
ORDER BY trade_date DESC LIMIT 5`, market)
	if err != nil {
		return nil
	}
	defer rows.Close()
	sum := 0.0
	n := 0
	for rows.Next() {
		var v sql.NullFloat64
		if err := rows.Scan(&v); err != nil || !v.Valid {
			continue
		}
		sum += v.Float64
		n++
	}
	if n == 0 {
		return nil
	}
	avg := sum / float64(n)
	return &avg
}

func (s *Service) countTop50(ctx context.Context, market, tradeDate string) (int, error) {
	var n int
	err := s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM market_top50_snapshot WHERE market=? AND trade_date=?`, market, tradeDate).Scan(&n)
	return n, err
}

func (s *Service) persistHeat(ctx context.Context, result heat.CollectResult) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()
	asOf := time.Now().In(beijingLoc())
	meta := heat.MarketMeta[result.Market]
	weightsJSON, _ := json.Marshal(s.heatWeights(ctx))
	_, err = tx.ExecContext(ctx, `
INSERT INTO market_heat_daily (
  market, trade_date, index_symbol, index_name, index_change_pct, total_turnover,
  advance_count, decline_count, flat_count, heat_score, heat_summary, currency,
  filter_rule, weights_json, as_of_time, status, message, create_time, update_time
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
ON DUPLICATE KEY UPDATE
  index_symbol=VALUES(index_symbol), index_name=VALUES(index_name),
  index_change_pct=VALUES(index_change_pct), total_turnover=VALUES(total_turnover),
  advance_count=VALUES(advance_count), decline_count=VALUES(decline_count),
  flat_count=VALUES(flat_count), heat_score=VALUES(heat_score),
  heat_summary=VALUES(heat_summary), currency=VALUES(currency),
  filter_rule=VALUES(filter_rule), weights_json=VALUES(weights_json),
  as_of_time=VALUES(as_of_time), status=VALUES(status), message=VALUES(message),
  update_time=VALUES(update_time)`,
		result.Market, result.TradeDate, meta.IndexSymbol, meta.IndexName,
		nullFloat(result.IndexChange), nullFloat(result.TotalTurnover),
		result.Advance, result.Decline, result.Flat, result.HeatScore, result.Summary,
		meta.Currency, meta.CapRule, string(weightsJSON), asOf, result.Status, result.Message,
		asOf, asOf,
	)
	if err != nil {
		return fmt.Errorf("upsert heat: %w", err)
	}
	if _, err := tx.ExecContext(ctx, `DELETE FROM market_top50_snapshot WHERE market=? AND trade_date=?`, result.Market, result.TradeDate); err != nil {
		return fmt.Errorf("clear top50: %w", err)
	}
	for _, item := range result.Top50 {
		if _, err := tx.ExecContext(ctx, `
INSERT INTO market_top50_snapshot (
  market, trade_date, rank_no, symbol, name, market_cap, turnover, change_pct, last,
  change_amount, turnover_rate, volume_ratio, amplitude, pe, main_net_inflow,
  currency, as_of_time, create_time
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
			result.Market, result.TradeDate, item.RankNo, item.Symbol, item.Name,
			nullFloat(item.MarketCap), nullFloat(item.Turnover), nullFloat(item.ChangePct),
			nullFloat(item.Last), nullFloat(item.ChangeAmount), nullFloat(item.TurnoverRate),
			nullFloat(item.VolumeRatio), nullFloat(item.Amplitude), nullFloat(item.PE),
			nullFloat(item.MainNetInflow), item.Currency, asOf, asOf,
		); err != nil {
			return fmt.Errorf("insert top50 %s: %w", item.Symbol, err)
		}
	}
	return tx.Commit()
}

func nullFloat(v *float64) any {
	if v == nil {
		return nil
	}
	return *v
}

func beijingLoc() *time.Location {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		return time.FixedZone("CST", 8*3600)
	}
	return loc
}
