package autoscan

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/platform"
	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/redis/go-redis/v9"
)

const minConfidenceDefault = 65

type Keys struct {
	CredentialKey string
	JWTSecret     string
	AppEnv        string
}

type StrategyEvaluator struct {
	Delegate *delegate.PythonClient
}

type StrategySignal struct {
	Symbol     string
	Market     string
	Signal     string
	Score      float64
	Confidence int
	Reason     string
	Price      float64
}

func (s *StrategyEvaluator) Evaluate(ctx context.Context, profile string, userID int, targets []platform.Target) ([]StrategySignal, error) {
	if s == nil || s.Delegate == nil {
		return nil, fmt.Errorf("strategy evaluate client is not configured")
	}
	symbols := make([]map[string]string, 0, len(targets))
	for _, t := range targets {
		symbols = append(symbols, map[string]string{"symbol": t.Symbol, "market": t.Market})
	}
	out, err := s.Delegate.Run(ctx, "strategy_evaluate", map[string]interface{}{
		"profile": profile, "userId": userID, "symbols": symbols,
	})
	if err != nil {
		return nil, err
	}
	raw := out["result"]
	if raw == nil {
		raw = out["signals"]
	}
	result, _ := raw.(map[string]interface{})
	var list []interface{}
	if result != nil {
		list, _ = result["signals"].([]interface{})
	}
	if list == nil {
		if direct, ok := out["signals"].([]interface{}); ok {
			list = direct
		}
	}
	signals := make([]StrategySignal, 0, len(list))
	for _, item := range list {
		m, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		sig := StrategySignal{
			Symbol:     strings.TrimSpace(fmt.Sprint(m["symbol"])),
			Market:     strings.ToUpper(strings.TrimSpace(fmt.Sprint(m["market"]))),
			Signal:     strings.ToUpper(strings.TrimSpace(fmt.Sprint(m["signal"]))),
			Score:      asFloat(m["score"]),
			Confidence: int(asFloat(m["confidence"])),
			Reason:     fmt.Sprint(m["reason"]),
			Price:      asFloat(m["price"]),
		}
		if sig.Market == "" || sig.Market == "<NIL>" {
			sig.Market = "US"
		}
		if sig.Reason == "<nil>" {
			sig.Reason = ""
		}
		signals = append(signals, sig)
	}
	return signals, nil
}

type RunInput struct {
	UserID          int
	Profile         string
	Source          string
	Execute         *bool
	CustomSymbols   []platform.Target
	CustomConfig    map[string]interface{}
}

func RunWatchlistCycle(ctx context.Context, repo *platform.Repo, broker tradeexec.Broker, strategy *StrategyEvaluator, rdb *redis.Client, keys Keys, in RunInput) (map[string]interface{}, error) {
	started := time.Now()
	userID := in.UserID
	if userID <= 0 {
		userID = 1
	}
	profile := repo.BoundProfile(ctx, userID, in.Profile)
	settings := repo.LoadSettings(ctx, userID)
	cycleID := fmt.Sprintf("cycle_%s_%s", started.Format("20060102_150405"), uuid.NewString()[:6])
	cfg := tradeexec.MergeRuntimeConfig(in.CustomConfig)
	cfg["strategy_profile"] = profile
	creds, _ := repo.LoadCreds(ctx, userID, keys.CredentialKey, keys.JWTSecret, keys.AppEnv)

	targets := resolveTargets(ctx, repo, userID, in.CustomSymbols)
	if len(targets) == 0 {
		msg := fmt.Sprintf("用户 %d 扫描池为空（美/港热度 Top50 且无可用自选）。A 股不参与自动交易。", userID)
		finished := time.Now()
		_ = repo.InsertRunLog(ctx, userID, map[string]interface{}{
			"cycle_id": cycleID, "source": in.Source, "strategy_profile": profile,
			"target_count": 0, "evaluated_count": 0, "opportunity_count": 0, "submitted_orders_count": 0,
			"status": "skipped", "message": msg, "started_at": started, "finished_at": finished,
			"guardrail_snapshot": "{}", "candidates_snapshot": "[]", "opportunities_snapshot": "[]", "skipped_reasons": mustJSON([]map[string]string{{"symbol": "*", "reason": msg}}),
		})
		return map[string]interface{}{
			"ok": true, "cycleId": cycleID, "source": in.Source, "submittedOrdersCount": 0,
			"message": msg, "candidates": []interface{}{}, "opportunities": []interface{}{},
			"skippedReasons": []map[string]string{{"symbol": "*", "reason": msg}},
		}, nil
	}

	signals, err := strategy.Evaluate(ctx, profile, userID, targets)
	if err != nil {
		return nil, err
	}
	minConf := asCfgInt(cfg["min_confidence"], minConfidenceDefault)
	candidates := make([]map[string]interface{}, 0)
	opportunities := make([]map[string]interface{}, 0)
	for _, item := range signals {
		decision := strings.ToUpper(item.Signal)
		conf := item.Confidence
		isOpp := (decision == "BUY" || decision == "SELL") && conf >= minConf
		if isOpp && !tradeexec.IsAutoTradeMarket(item.Market, item.Symbol) {
			isOpp = false
		}
		row := map[string]interface{}{
			"symbol": item.Symbol, "market": item.Market, "price": item.Price,
			"signal": decision, "confidence": conf, "reason": item.Reason,
			"isOpportunity": isOpp, "score": map[string]interface{}{"total": item.Score},
		}
		candidates = append(candidates, row)
		if isOpp {
			opportunities = append(opportunities, row)
		}
	}
	sortOpportunities(opportunities)

	shouldExecute := settings.AutoTradeEnabled
	if in.Execute != nil {
		shouldExecute = *in.Execute
	}
	configured := creds.Configured()
	canSubmit, submitBlock := tradeexec.ResolveSubmitPermission(shouldExecute, configured, settings.AutoTradeEnabled)
	haltMsg := tradeexec.HaltBlockReason(readHalt(ctx, rdb))
	skipped := make([]map[string]string, 0)
	if haltMsg != "" {
		canSubmit = false
		submitBlock = haltMsg
		skipped = append(skipped, map[string]string{"symbol": "*", "reason": haltMsg})
	}

	fx := tradeexec.NewFxRates()
	var account tradeexec.Account
	var positions []tradeexec.Position
	if configured {
		if quotes, qerr := broker.RealtimeQuotes(ctx, creds, []string{"USDHKD", "USDCNH"}, "US"); qerr == nil {
			fx.USDHKD, fx.Sources["USDHKD"] = tradeexec.PickRateFromQuotes(quotes, "USDHKD", tradeexec.FallbackUSDHKD)
			fx.USDCNY, fx.Sources["USDCNH"] = tradeexec.PickRateFromQuotes(quotes, "USDCNH", tradeexec.FallbackUSDCNY)
		}
		if acct, aerr := broker.AccountBalance(ctx, creds); aerr == nil {
			account = acct
		}
	}
	netAssets := tradeexec.PickNetAssets(account, fx)
	availableCash := tradeexec.PickAvailableCash(account, fx)
	maxDaily := tradeexec.DailyBuyCap(netAssets, settings.DailyBuyRatio)
	maxPerSymbol := tradeexec.SymbolPositionCap(netAssets, settings.MaxSymbolPositionPct)
	todayOrders, todayNotional, _ := repo.TodayStats(ctx, userID)
	if canSubmit && len(opportunities) > 0 {
		if pos, perr := broker.Positions(ctx, creds); perr == nil {
			positions = pos
		}
		if netAssets <= 0 {
			canSubmit = false
			skipped = append(skipped, map[string]string{"symbol": "*", "reason": fmt.Sprintf("账户净资产为 0，无法按仓位 %d%% 计算日内买入额度", int(settings.DailyBuyRatio*100))})
		}
	}
	totalMV := tradeexec.TotalPositionMarketValue(positions, &fx, nil)
	grossRoom := tradeexec.RemainingGrossRoom(netAssets, totalMV, tradeexec.MaxGrossExposurePct)
	if canSubmit && len(opportunities) > 0 && grossRoom < tradeexec.MinTargetAmountUSD {
		canSubmit = false
		skipped = append(skipped, map[string]string{"symbol": "*", "reason": fmt.Sprintf("总持仓 $%.0f 已达或超过净资产 $%.0f，停止买入", totalMV, netAssets)})
	}
	if canSubmit && len(opportunities) > 0 && availableCash < tradeexec.MinTargetAmountUSD {
		canSubmit = false
		skipped = append(skipped, map[string]string{"symbol": "*", "reason": fmt.Sprintf("可用现金不足 ($%.2f)，停止买入", availableCash)})
	}

	submitted := 0
	todayBought, _ := repo.TodayBought(ctx, userID)
	maxSymbols := asCfgInt(cfg["max_symbols"], 3)
	source := in.Source
	if source == "" {
		source = "manual_api"
	}
	if canSubmit && len(opportunities) > 0 {
		cands := opportunities
		if len(cands) > maxSymbols {
			cands = cands[:maxSymbols]
		}
		priceMap := map[string]float64{}
		need := make([]string, 0, len(cands))
		for _, opp := range cands {
			sym := fmt.Sprint(opp["symbol"])
			mkt := fmt.Sprint(opp["market"])
			need = append(need, tradeexec.ToLongbridgeSymbol(sym, mkt))
		}
		if quotes, qerr := broker.RealtimeQuotes(ctx, creds, need, "US"); qerr == nil {
			for _, opp := range cands {
				sym := fmt.Sprint(opp["symbol"])
				mkt := fmt.Sprint(opp["market"])
				priceMap[sym] = tradeexec.QuoteLastForSymbol(quotes, sym, mkt, len(cands))
			}
		}
		for _, opp := range cands {
			symbol := fmt.Sprint(opp["symbol"])
			market := fmt.Sprint(opp["market"])
			side := strings.ToUpper(fmt.Sprint(opp["signal"]))
			signalPrice, _ := opp["price"].(float64)
			if reason := tradeexec.CheckDailyLimits(todayOrders, 10, todayNotional, maxDaily); reason != "" {
				skipped = append(skipped, map[string]string{"symbol": symbol, "reason": reason})
				continue
			}
			rt := priceMap[symbol]
			if rt <= 0 {
				skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "未能获取券商有效盘中实时报价，为防滑点拒绝下单"})
				continue
			}
			if tradeexec.SlippageExceeded(signalPrice, rt, 0.03) {
				skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "实时价偏离信号价过大"})
				continue
			}
			quantity := 0
			if side == "SELL" {
				pos := tradeexec.MatchPosition(positions, symbol, market)
				quantity = int(tradeexec.PositionQuantity(pos))
				if quantity <= 0 {
					skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "无可用持仓，跳过卖出"})
					continue
				}
			} else {
				if !tradeexec.IsAutoTradeMarket(market, symbol) {
					skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "A股不参与自动交易"})
					continue
				}
				if tradeexec.ShouldSkipDuplicateBuy(symbol, todayBought) {
					skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "今日已买入该标的，跳过重复加仓"})
					continue
				}
				pos := tradeexec.MatchPosition(positions, symbol, market)
				if tradeexec.ShouldSkipHeldBuy(pos) {
					skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "已持有该标的，跳过重复买入"})
					continue
				}
				existing := tradeexec.ExistingPositionMarketValue(pos, rt, &fx)
				room := tradeexec.SymbolBuyRoom(netAssets, settings.MaxSymbolPositionPct, existing)
				if room < tradeexec.MinTargetAmountUSD {
					skipped = append(skipped, map[string]string{"symbol": symbol, "reason": fmt.Sprintf("已达单标的仓位上限 (%d%% NAV)", int(settings.MaxSymbolPositionPct*100))})
					continue
				}
				remainingDaily := maxDaily - todayNotional
				if remainingDaily < 0 {
					remainingDaily = 0
				}
				grossRoom = tradeexec.RemainingGrossRoom(netAssets, totalMV, tradeexec.MaxGrossExposurePct)
				target := remainingDaily
				if room < target {
					target = room
				}
				if grossRoom < target {
					target = grossRoom
				}
				if availableCash < target {
					target = availableCash
				}
				if target < tradeexec.MinTargetAmountUSD {
					skipped = append(skipped, map[string]string{"symbol": symbol, "reason": fmt.Sprintf("剩余额度不足 ($%.2f)：日内/单票/总仓位/现金", target)})
					continue
				}
				quantity = tradeexec.BuyQuantityFromUSD(target, rt, market, fx)
			}
			orderPrice := tradeexec.RoundLimitPrice(rt, market)
			if orderPrice <= 0 {
				skipped = append(skipped, map[string]string{"symbol": symbol, "reason": "委托价无效，跳过下单"})
				continue
			}
			res := broker.SubmitOrder(ctx, creds, tradeexec.SubmitReq{
				Symbol: symbol, Side: side, Quantity: float64(quantity), OrderType: "LO", Price: orderPrice, Market: market,
			})
			status := "rejected"
			orderID := ""
			errText := res.Message
			if res.OK {
				status = "submitted"
				orderID = res.OrderID
				errText = ""
				submitted++
				todayOrders++
				todayNotional += tradeexec.OrderNotional(float64(quantity), orderPrice)
				code, _ := tradeexec.ParseSymbolMarket(symbol, market)
				if todayBought == nil {
					todayBought = map[string]struct{}{}
				}
				todayBought[code] = struct{}{}
				orderCur := fx.OrderCurrency(market)
				totalMV += fx.ToUSD(float64(quantity)*orderPrice, orderCur)
				availableCash -= fx.ToUSD(float64(quantity)*orderPrice, orderCur)
			}
			conf := int(asFloat(opp["confidence"]))
			_ = repo.InsertDecision(ctx, userID, cycleID, symbol, market, side, quantity, orderPrice, conf, status, fmt.Sprint(opp["reason"]), source, orderID, errText)
		}
	}

	finished := time.Now()
	guard := map[string]interface{}{
		"todayOrdersCount": todayOrders, "maxDailyOrders": 10,
		"todayNotionalAmount": todayNotional, "maxDailyNotionalAmount": maxDaily,
		"maxSymbols": maxSymbols, "maxAmountPerSymbol": maxPerSymbol,
		"netAssets": netAssets, "availableCash": availableCash,
		"autoTradeEnabled": settings.AutoTradeEnabled, "configured": configured,
		"submitAllowed": canSubmit, "submitBlockReason": submitBlock,
	}
	msg := fmt.Sprintf("扫描 %d 标的，机会 %d，提交 %d", len(targets), len(opportunities), submitted)
	_ = repo.InsertRunLog(ctx, userID, map[string]interface{}{
		"cycle_id": cycleID, "source": source, "strategy_profile": profile,
		"target_count": len(targets), "evaluated_count": len(candidates), "opportunity_count": len(opportunities),
		"submitted_orders_count": submitted, "status": "completed",
		"guardrail_snapshot": mustJSON(guard), "candidates_snapshot": mustJSON(candidates),
		"opportunities_snapshot": mustJSON(opportunities), "skipped_reasons": mustJSON(skipped),
		"message": msg, "started_at": started, "finished_at": finished,
	})
	return map[string]interface{}{
		"ok": true, "cycleId": cycleID, "source": source, "strategyProfile": profile,
		"targetCount": len(targets), "evaluatedCount": len(candidates),
		"opportunityCount": len(opportunities), "submittedOrdersCount": submitted,
		"submitAllowed": canSubmit, "message": msg,
		"durationSeconds": finished.Sub(started).Seconds(),
	}, nil
}

func resolveTargets(ctx context.Context, repo *platform.Repo, userID int, custom []platform.Target) []platform.Target {
	if len(custom) > 0 {
		return mergeTargets(custom)
	}
	heat, _ := repo.HeatUniverse(ctx)
	watch, _ := repo.EnabledWatchlist(ctx, userID)
	return mergeTargets(heat, watch)
}

func mergeTargets(parts ...[]platform.Target) []platform.Target {
	seen := map[string]struct{}{}
	var out []platform.Target
	for _, part := range parts {
		for _, t := range part {
			if t.Symbol == "" || !tradeexec.IsAutoTradeMarket(t.Market, t.Symbol) {
				continue
			}
			code, mkt := tradeexec.ParseSymbolMarket(t.Symbol, t.Market)
			key := strings.ToUpper(code) + "|" + mkt
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			out = append(out, platform.Target{Symbol: code, Market: mkt, Name: t.Name})
		}
	}
	return out
}

func sortOpportunities(rows []map[string]interface{}) {
	for i := 0; i < len(rows); i++ {
		for j := i + 1; j < len(rows); j++ {
			if oppKey(rows[j]) > oppKey(rows[i]) {
				rows[i], rows[j] = rows[j], rows[i]
			}
		}
	}
}

func oppKey(row map[string]interface{}) float64 {
	conf := asFloat(row["confidence"])
	score := 0.0
	if m, ok := row["score"].(map[string]interface{}); ok {
		score = asFloat(m["total"])
	}
	return conf*1e6 + score
}

func asCfgInt(v interface{}, fallback int) int {
	switch x := v.(type) {
	case int:
		return x
	case float64:
		return int(x)
	default:
		return fallback
	}
}

func asFloat(v interface{}) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case float32:
		return float64(x)
	case int:
		return float64(x)
	case int64:
		return float64(x)
	case json.Number:
		f, _ := x.Float64()
		return f
	default:
		return 0
	}
}

func readHalt(ctx context.Context, rdb *redis.Client) tradeexec.HaltState {
	if rdb == nil {
		return tradeexec.HaltState{}
	}
	raw, err := rdb.Get(ctx, tradeexec.HaltRedisKey).Result()
	if err != nil || raw == "" {
		return tradeexec.HaltState{}
	}
	return tradeexec.ParseHalt(raw)
}

func mustJSON(v interface{}) string {
	raw, _ := json.Marshal(v)
	return string(raw)
}
