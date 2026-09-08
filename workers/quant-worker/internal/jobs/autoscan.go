package jobs

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
	"github.com/redis/go-redis/v9"
)

const minConfidenceDefault = 65

func RunAutoTradeScan(ctx context.Context, repo *Repo, broker tradeexec.Broker, strategy StrategyClient, rdb *redis.Client, keys EncKeys, payload map[string]interface{}) (map[string]interface{}, error) {
	profile := payloadString(payload, "profile")
	userID := payloadInt(payload, "userId")
	var users []int
	if userID > 0 {
		users = []int{userID}
	} else {
		watch, _ := repo.DistinctWatchlistUsers(ctx)
		keysUsers, _ := repo.ListConfiguredUserIDs(ctx)
		users = uniqueInts(watch, keysUsers)
		if len(users) == 0 {
			users = []int{1}
		}
	}
	var last map[string]interface{}
	for _, uid := range users {
		code := repo.BoundProfile(ctx, uid, profile)
		one, err := runWatchlistCycle(ctx, repo, broker, strategy, rdb, keys, uid, code)
		if err != nil {
			return nil, err
		}
		last = one
	}
	if last == nil {
		last = map[string]interface{}{}
	}
	last["profile"] = profile
	last["userId"] = userID
	return last, nil
}

func runWatchlistCycle(ctx context.Context, repo *Repo, broker tradeexec.Broker, strategy StrategyClient, rdb *redis.Client, keys EncKeys, userID int, profile string) (map[string]interface{}, error) {
	started := time.Now()
	settings := repo.LoadSettings(ctx, userID)
	cycleID := fmt.Sprintf("cycle_%s_%s", started.Format("20060102_150405"), uuid.NewString()[:6])
	cfg := tradeexec.MergeRuntimeConfig(nil)
	cfg["strategy_profile"] = profile
	creds, _ := repo.LoadCreds(ctx, userID, keys.CredentialKey, keys.JWTSecret, keys.AppEnv)

	heat, _ := repo.HeatUniverse(ctx)
	watch, _ := repo.EnabledWatchlist(ctx, userID)
	targets := mergeTargets(heat, watch)
	signals, err := strategy.Evaluate(ctx, profile, userID, targets)
	if err != nil {
		return nil, err
	}
	minConf := asCfgInt(cfg["min_confidence"], minConfidenceDefault)
	var candidates []map[string]interface{}
	var opportunities []map[string]interface{}
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
	configured := creds.Configured()
	canSubmit, submitBlock := tradeexec.ResolveSubmitPermission(shouldExecute, configured, settings.AutoTradeEnabled)
	haltMsg := tradeexec.HaltBlockReason(readHalt(ctx, rdb))
	var skipped []map[string]string
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
	var decisions []map[string]interface{}
	todayBought, _ := repo.TodayBought(ctx, userID)
	maxSymbols := asCfgInt(cfg["max_symbols"], 3)
	if canSubmit && len(opportunities) > 0 {
		cands := opportunities
		if len(cands) > maxSymbols {
			cands = cands[:maxSymbols]
		}
		priceMap := map[string]float64{}
		var need []string
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
			conf, _ := opp["confidence"].(int)
			_ = repo.InsertDecision(ctx, DecisionRow{
				CycleID: cycleID, UserID: userID, Symbol: symbol, Market: market, Side: side,
				Quantity: quantity, Price: orderPrice, Confidence: conf, Status: status,
				Reason: fmt.Sprint(opp["reason"]), Source: "scheduler", OrderID: orderID, Error: errText,
			})
			decisions = append(decisions, map[string]interface{}{
				"symbol": symbol, "side": side, "ok": res.OK, "orderId": orderID, "message": res.Message,
			})
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
	_ = repo.InsertRunLog(ctx, RunLog{
		CycleID: cycleID, UserID: userID, Source: "scheduler", Profile: profile,
		TargetCount: len(targets), EvaluatedCount: len(candidates), OpportunityCount: len(opportunities),
		Submitted: submitted, Status: "completed",
		GuardrailJSON: mustJSON(guard), CandidatesJSON: mustJSON(candidates),
		OpportunitiesJSON: mustJSON(opportunities), SkippedJSON: mustJSON(skipped),
		Message: msg, Started: started, Finished: finished,
	})
	return map[string]interface{}{
		"ok": true, "cycleId": cycleID, "source": "scheduler", "strategyProfile": profile,
		"targetCount": len(targets), "evaluatedCount": len(candidates),
		"opportunityCount": len(opportunities), "submittedOrdersCount": submitted,
		"submitAllowed": canSubmit, "message": msg,
		"durationSeconds": finished.Sub(started).Seconds(),
	}, nil
}

func mergeTargets(parts ...[]Target) []Target {
	seen := map[string]struct{}{}
	var out []Target
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
			out = append(out, Target{Symbol: code, Market: mkt, Name: t.Name})
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
	conf := 0.0
	switch v := row["confidence"].(type) {
	case int:
		conf = float64(v)
	case float64:
		conf = v
	}
	score := 0.0
	if m, ok := row["score"].(map[string]interface{}); ok {
		switch v := m["total"].(type) {
		case float64:
			score = v
		case int:
			score = float64(v)
		}
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
