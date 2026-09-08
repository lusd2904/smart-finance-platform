package store

import (
	"context"
	"sort"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factor"
)

type factorSnap struct {
	symbol  string
	market  string
	name    string
	asOf    string
	score   factor.Score
	metrics factor.Metrics
}

func (s *Service) RunFactorScan(ctx context.Context, profile string) (map[string]any, error) {
	profile = factor.NormalizeProfile(profile)
	cfg := s.loadProfileConfig(ctx, profile, 0)
	weights := factor.MergeProfileConfig(profile, cfg)
	universe := factor.ScanUniverse()

	items := make([]symbolMarket, 0, len(universe))
	for _, inst := range universe {
		items = append(items, symbolMarket{inst.Symbol, inst.Market})
	}
	klines, skipped := s.prefetchKlines(ctx, items, "-1y", 320)
	skipSet := map[string]bool{}
	for _, m := range skipped {
		skipSet[m] = true
	}

	snaps := []factorSnap{}
	failed := []map[string]string{}
	for _, inst := range universe {
		if skipSet[inst.Market] {
			failed = append(failed, map[string]string{"symbol": inst.Symbol, "reason": "K线拉取失败"})
			continue
		}
		bars := toFactorBars(klines[inst.Symbol+"|"+inst.Market])
		res := factor.ComputeFromKlines(bars, profile, weights)
		if !res.OK {
			failed = append(failed, map[string]string{"symbol": inst.Symbol, "reason": res.Reason})
			continue
		}
		snaps = append(snaps, factorSnap{
			symbol: inst.Symbol, market: inst.Market, name: inst.Name,
			asOf: res.Metrics.TradeDate, score: res.Score, metrics: res.Metrics,
		})
	}

	csRows := make([]factor.CSRow, len(snaps))
	for i, sn := range snaps {
		csRows[i] = factor.CSRow{
			Symbol: sn.symbol, Return20: sn.metrics.Get("return20", 0),
			RSI14: sn.metrics.Get("rsi14", 0), VolumeRatio20: sn.metrics.Get("volumeRatio20", 0),
			DistanceHigh20: sn.metrics.Get("distanceHigh20", 0), Alpha101: sn.metrics.Alpha101,
		}
	}
	factor.AttachCrossSection(csRows)

	if len(snaps) > 0 {
		if err := s.persistFactorSnaps(ctx, snaps, csRows); err != nil {
			return nil, err
		}
	}
	okItems := []map[string]any{}
	for i, sn := range snaps {
		okItems = append(okItems, map[string]any{
			"symbol": sn.symbol, "market": sn.market, "name": sn.name,
			"total": sn.score.Total, "riskLevel": sn.score.RiskLevel,
			"trendDirection": sn.score.TrendDirection,
			"alpha101Count":  sn.metrics.Alpha101N, "alpha158Count": sn.metrics.Alpha158N,
			"alphaCsCount":   csRows[i].AlphaCsCount,
		})
	}
	sort.Slice(okItems, func(i, j int) bool {
		ti, _ := okItems[i]["total"].(float64)
		tj, _ := okItems[j]["total"].(float64)
		return ti > tj
	})
	failedCap := failed
	if len(failedCap) > 20 {
		failedCap = failedCap[:20]
	}
	payload := map[string]any{
		"asOf": beijingNow(), "profile": profile,
		"symbolCount": len(okItems), "failedCount": len(failed),
		"items": okItems, "failed": failedCap, "readModelVersion": readModelV,
	}
	if err := s.addReadmodel(ctx, "factors", mustJSON(payload)); err != nil {
		return nil, err
	}
	if err := s.putScheduled(ctx, "factors", payload, factorTTL); err != nil {
		return nil, err
	}
	overview := s.buildOverview(ctx, payload)
	if err := s.addReadmodel(ctx, "overview", mustJSON(overview)); err != nil {
		return nil, err
	}
	_ = s.putScheduled(ctx, "overview", overview, overviewTTL)
	return payload, nil
}

func (s *Service) persistFactorSnaps(ctx context.Context, snaps []factorSnap, cs []factor.CSRow) error {
	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback() }()

	for i, sn := range snaps {
		asOf := sn.asOf
		if len(asOf) > 16 {
			asOf = asOf[:16]
		}
		alphaPayload := map[string]any{
			"alpha101Count": sn.metrics.Alpha101N,
			"alpha158Count": sn.metrics.Alpha158N,
			"alpha158Top":   factor.TopAlpha(sn.metrics.Alpha158, 12),
		}
		if i < len(cs) && cs[i].AlphaCs != nil {
			alphaPayload["alphaCs"] = cs[i].AlphaCs
		}
		var snapshotID int64
		err := tx.QueryRowContext(ctx, `
SELECT snapshot_id FROM quant_factor_snapshot WHERE symbol = ? AND market = ? LIMIT 1`,
			sn.symbol, sn.market).Scan(&snapshotID)
		if err == nil && snapshotID > 0 {
			_, err = tx.ExecContext(ctx, `
UPDATE quant_factor_snapshot
SET as_of=?, score_total=?, risk_level=?, trend_direction=?,
    alpha101_count=?, alpha158_count=?, score_json=?, alpha_json=?, create_time=NOW()
WHERE snapshot_id=?`,
				asOf, sn.score.Total, sn.score.RiskLevel, sn.score.TrendDirection,
				sn.metrics.Alpha101N, sn.metrics.Alpha158N, mustJSON(sn.score), mustJSON(alphaPayload), snapshotID)
		} else {
			_, err = tx.ExecContext(ctx, `
INSERT INTO quant_factor_snapshot
(symbol, market, as_of, score_total, risk_level, trend_direction,
 alpha101_count, alpha158_count, score_json, alpha_json, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())`,
				sn.symbol, sn.market, asOf, sn.score.Total, sn.score.RiskLevel, sn.score.TrendDirection,
				sn.metrics.Alpha101N, sn.metrics.Alpha158N, mustJSON(sn.score), mustJSON(alphaPayload))
		}
		if err != nil {
			return err
		}
		if _, err = tx.ExecContext(ctx, `DELETE FROM quant_alpha101_value WHERE symbol=? AND market=?`, sn.symbol, sn.market); err != nil {
			return err
		}
		if _, err = tx.ExecContext(ctx, `DELETE FROM quant_alpha158_value WHERE symbol=? AND market=?`, sn.symbol, sn.market); err != nil {
			return err
		}
		for k, v := range sn.metrics.Alpha101 {
			if _, err = tx.ExecContext(ctx, `
INSERT INTO quant_alpha101_value (symbol, market, as_of, factor_key, factor_value, create_time)
VALUES (?, ?, ?, ?, ?, NOW())`, sn.symbol, sn.market, asOf, truncate(k, 32), v); err != nil {
				return err
			}
		}
		for k, v := range sn.metrics.Alpha158 {
			if _, err = tx.ExecContext(ctx, `
INSERT INTO quant_alpha158_value (symbol, market, as_of, factor_key, factor_value, create_time)
VALUES (?, ?, ?, ?, ?, NOW())`, sn.symbol, sn.market, asOf, truncate(k, 32), v); err != nil {
				return err
			}
		}
	}
	return tx.Commit()
}

func (s *Service) buildOverview(ctx context.Context, factorScan map[string]any) map[string]any {
	board := s.latestReadmodel(ctx, "board")
	items, _ := board["items"].([]any)
	if len(items) > 16 {
		items = items[:16]
	}
	return map[string]any{
		"configured":       false,
		"asset":            map[string]any{"configured": false},
		"position":         map[string]any{"count": 0, "positions": []any{}},
		"factorScan":       factorScan,
		"board":            map[string]any{"count": board["count"], "asOf": board["asOf"], "items": items},
		"refreshTime":      beijingNow(),
		"readModelVersion": readModelV,
		"source":           "scheduled",
	}
}

func (s *Service) replaceAlphaForSignal(ctx context.Context, symbol, market, asOf string, a101, a158 map[string]float64) error {
	if len(asOf) > 16 {
		asOf = asOf[:16]
	}
	if asOf == "" {
		asOf = strings.Split(beijingNow(), " ")[0]
	}
	if _, err := s.db.ExecContext(ctx, `DELETE FROM quant_alpha101_value WHERE symbol=? AND market=?`, symbol, market); err != nil {
		return err
	}
	if _, err := s.db.ExecContext(ctx, `DELETE FROM quant_alpha158_value WHERE symbol=? AND market=?`, symbol, market); err != nil {
		return err
	}
	for k, v := range a101 {
		if _, err := s.db.ExecContext(ctx, `
INSERT INTO quant_alpha101_value (symbol, market, as_of, factor_key, factor_value, create_time)
VALUES (?, ?, ?, ?, ?, NOW())`, symbol, market, asOf, truncate(k, 32), v); err != nil {
			return err
		}
	}
	for k, v := range a158 {
		if _, err := s.db.ExecContext(ctx, `
INSERT INTO quant_alpha158_value (symbol, market, as_of, factor_key, factor_value, create_time)
VALUES (?, ?, ?, ?, ?, NOW())`, symbol, market, asOf, truncate(k, 32), v); err != nil {
			return err
		}
	}
	return nil
}
