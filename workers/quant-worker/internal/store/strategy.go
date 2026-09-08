package store

import (
	"context"
	"sort"
	"strings"

	"github.com/google/uuid"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factor"
)

func (s *Service) RunStrategy(ctx context.Context, payload map[string]any) (map[string]any, error) {
	override := payloadString(payload, "profile")
	userID := payloadInt(payload, "userId")
	symbols := payloadSymbols(payload)

	if userID > 0 {
		return s.runStrategyForUser(ctx, userID, override, symbols)
	}
	users, err := s.watchlistUsers(ctx)
	if err != nil {
		return nil, err
	}
	results := []map[string]any{}
	for _, uid := range users {
		one, err := s.runStrategyForUser(ctx, uid, override, symbols)
		if err != nil {
			results = append(results, map[string]any{"userId": uid, "error": err.Error()})
			continue
		}
		results = append(results, one)
	}
	return map[string]any{"userCount": len(users), "results": results}, nil
}

func (s *Service) runStrategyForUser(ctx context.Context, userID int, override string, symbols []string) (map[string]any, error) {
	profile := s.resolveProfile(ctx, userID, override)
	cfg := s.loadProfileConfig(ctx, profile, userID)

	type target struct {
		symbol, market, name string
	}
	targets := []target{}
	if len(symbols) > 0 {
		for _, sym := range symbols {
			if strings.TrimSpace(sym) != "" {
				targets = append(targets, target{strings.ToUpper(strings.TrimSpace(sym)), "US", ""})
			}
		}
	} else {
		watch, err := s.enabledWatchlist(ctx, userID)
		if err != nil {
			return nil, err
		}
		for _, w := range watch {
			targets = append(targets, target{w.Symbol, w.Market, w.Name})
		}
	}
	if len(targets) == 0 {
		return map[string]any{
			"runId": nil, "symbolsCount": 0, "signalCount": 0, "signals": []any{},
			"message": "无可用标的",
		}, nil
	}

	pairs := make([]symbolMarket, 0, len(targets))
	for _, t := range targets {
		pairs = append(pairs, symbolMarket{t.symbol, t.market})
	}
	klines, _ := s.prefetchKlines(ctx, pairs, "-1y", 320)

	signals := []factor.Signal{}
	for _, t := range targets {
		sig := factor.EvaluateSymbol(t.symbol, t.market, profile, toFactorBars(klines[t.symbol+"|"+t.market]), cfg)
		signals = append(signals, sig)
	}
	sort.Slice(signals, func(i, j int) bool { return signals[i].Score > signals[j].Score })
	actionable := 0
	for _, sig := range signals {
		if sig.Signal == "BUY" || sig.Signal == "SELL" {
			actionable++
		}
	}

	cycleID := strings.ReplaceAll(uuid.NewString(), "-", "")
	res, err := s.db.ExecContext(ctx, `
INSERT INTO quant_strategy_run (cycle_id, user_id, strategy_profile, symbols_count, signal_count, create_time)
VALUES (?, ?, ?, ?, ?, NOW())`, cycleID, userID, profile, len(signals), actionable)
	if err != nil {
		return nil, err
	}
	runID, _ := res.LastInsertId()
	for _, sig := range signals {
		summary := map[string]any{
			"score":         sig.ScoreDetail,
			"latestClose":   sig.Metrics.Get("latestClose", 0),
			"tradeDate":     sig.Metrics.TradeDate,
			"alpha101Count": sig.Metrics.Alpha101N,
			"alpha158Count": sig.Metrics.Alpha158N,
		}
		if _, err := s.db.ExecContext(ctx, `
INSERT INTO quant_strategy_signal
(run_id, user_id, symbol, signal, score, confidence, reason, factor_json, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW())`,
			runID, userID, sig.Symbol, sig.Signal, sig.Score, sig.Confidence,
			truncate(sig.Reason, 500), mustJSON(summary)); err != nil {
			return nil, err
		}
		if sig.OK {
			if err := s.replaceAlphaForSignal(ctx, sig.Symbol, sig.Market, sig.Metrics.TradeDate, sig.Metrics.Alpha101, sig.Metrics.Alpha158); err != nil {
				return nil, err
			}
		}
	}

	outSignals := []map[string]any{}
	for _, sig := range signals {
		outSignals = append(outSignals, map[string]any{
			"symbol": sig.Symbol, "market": sig.Market, "signal": sig.Signal,
			"score": sig.Score, "confidence": sig.Confidence, "reason": sig.Reason,
		})
	}
	return map[string]any{
		"runId": runID, "cycleId": cycleID, "profile": profile,
		"symbolsCount": len(signals), "signalCount": actionable,
		"signals": outSignals, "message": "策略执行完成",
	}, nil
}
