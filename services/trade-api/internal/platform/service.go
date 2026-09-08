package platform

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"math"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/backtest"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/delegate"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/influx"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/queue"
	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/redis/go-redis/v9"
)

const (
	validProfiles       = "conservative|balanced|aggressive"
	backtestMinBars     = 40
	backtestMinDays     = 60
	tradingDays         = 252
	minReturns          = 20
	maxPositionsTearsheet = 20
)

type Service struct {
	Repo          *Repo
	Influx        *influx.Client
	Delegate      *delegate.PythonClient
	Queue         *queue.Enqueuer
	Broker        tradeexec.Broker
	Redis         *redis.Client
	CredentialKey string
	JWTSecret     string
	AppEnv        string
}

func (s *Service) ListNotifications(ctx context.Context, userID, limit int) ([]map[string]interface{}, error) {
	rows, err := s.Repo.ListNotifications(ctx, userID, limit)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, r := range rows {
		out = append(out, map[string]interface{}{
			"id": r.ID, "title": r.Title, "content": r.Content,
			"level": r.Level, "category": r.Category, "read": r.Read, "createTime": r.CreateTime,
		})
	}
	return out, nil
}

func (s *Service) MarkNotificationRead(ctx context.Context, userID int, noticeID *int) (map[string]interface{}, error) {
	n, err := s.Repo.MarkNotificationsRead(ctx, userID, noticeID)
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{"updated": n}, nil
}

func (s *Service) ListNotices(ctx context.Context, userID, limit int) ([]map[string]interface{}, error) {
	return s.ListNotifications(ctx, userID, limit)
}

func (s *Service) MarkNoticeRead(ctx context.Context, userID int, noticeID *int) error {
	_, err := s.Repo.MarkNotificationsRead(ctx, userID, noticeID)
	return err
}

func (s *Service) RunBacktest(ctx context.Context, userID int, symbol, market string, days int, profile string) (map[string]interface{}, error) {
	if userID <= 0 {
		return map[string]interface{}{"ok": false, "message": "无法识别当前用户", "symbol": symbol}, nil
	}
	profile = normalizeProfile(profile)
	if s.Influx == nil {
		return map[string]interface{}{"ok": false, "message": "Influx 未配置", "symbol": symbol}, nil
	}
	window := days
	if window < backtestMinDays {
		window = backtestMinDays
	}
	bars, err := s.Influx.QueryKlines(ctx, market, symbol, fmt.Sprintf("-%dd", window), "now()", nil)
	if err != nil {
		return map[string]interface{}{"ok": false, "message": err.Error(), "symbol": symbol}, nil
	}
	if len(bars) < backtestMinBars {
		return map[string]interface{}{"ok": false, "message": fmt.Sprintf("%s K线不足，请先同步行情", symbol), "symbol": symbol}, nil
	}
	klines := make([]backtest.Kline, 0, len(bars))
	for _, b := range bars {
		if b.Close == nil || *b.Close <= 0 {
			continue
		}
		klines = append(klines, backtest.Kline{Date: b.Date, Close: *b.Close})
	}
	signals := backtest.FactorSignals(klines, profile, nil)
	sim := backtest.SimulateLongOnly(klines, signals, 100000, backtest.DefaultFee, backtest.DefaultSlip)
	strategyName := "factor-8family:" + profile
	equityJSON, _ := json.Marshal(trimEquity(sim.Equity, 60))
	id, err := s.Repo.AddBacktestRun(ctx, userID, map[string]interface{}{
		"symbol": symbol, "market": market, "days": days, "strategy": strategyName,
		"trades": sim.Trades, "return_pct": sim.ReturnPct, "final_equity": sim.FinalEquity,
		"max_drawdown": sim.MaxDrawdown, "win_rate": sim.WinRate, "equity_curve_json": string(equityJSON),
		"message": fmt.Sprintf("回测完成（%s）", strategyName),
	})
	if err != nil {
		return nil, err
	}
	_ = s.Repo.AddNotification(ctx, userID, fmt.Sprintf("回测完成 %s", symbol),
		fmt.Sprintf("%s · 收益 %.2f%% · 最大回撤 %.2f%% · 交易 %d 次", strategyName, sim.ReturnPct, sim.MaxDrawdown, sim.Trades),
		"success", "backtest")
	return map[string]interface{}{
		"id": id, "symbol": symbol, "market": market, "days": days,
		"trades": sim.Trades, "returnPct": sim.ReturnPct, "finalEquity": sim.FinalEquity,
		"maxDrawdown": sim.MaxDrawdown, "winRate": sim.WinRate, "equity": sim.Equity,
		"message": fmt.Sprintf("回测完成（%s）", strategyName), "ok": true,
	}, nil
}

func (s *Service) ListBacktests(ctx context.Context, userID int) ([]map[string]interface{}, error) {
	rows, err := s.Repo.ListBacktests(ctx, userID, 50)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, r := range rows {
		out = append(out, map[string]interface{}{
			"id": r.ID, "symbol": r.Symbol, "market": r.Market, "days": r.Days,
			"strategy": r.Strategy, "trades": r.Trades, "returnPct": r.ReturnPct,
			"finalEquity": r.FinalEquity, "maxDrawdown": r.MaxDrawdown, "winRate": r.WinRate,
			"message": r.Message, "createTime": r.CreateTime,
		})
	}
	return out, nil
}

func (s *Service) GetBacktest(ctx context.Context, userID, runID int) (map[string]interface{}, error) {
	r, err := s.Repo.GetBacktest(ctx, userID, runID)
	if err != nil {
		return nil, err
	}
	if r == nil {
		return nil, fmt.Errorf("回测记录不存在")
	}
	var equity []interface{}
	_ = json.Unmarshal([]byte(r.EquityCurve), &equity)
	return map[string]interface{}{
		"id": r.ID, "symbol": r.Symbol, "market": r.Market, "days": r.Days,
		"strategy": r.Strategy, "trades": r.Trades, "returnPct": r.ReturnPct,
		"finalEquity": r.FinalEquity, "maxDrawdown": r.MaxDrawdown, "winRate": r.WinRate,
		"equity": equity, "message": r.Message, "createTime": r.CreateTime,
	}, nil
}

func (s *Service) ListStrategyProfiles(ctx context.Context, userID int) ([]map[string]interface{}, error) {
	_ = s.Repo.EnsureSeedProfiles(ctx)
	rows, err := s.Repo.ListStrategyProfiles(ctx)
	if err != nil {
		return nil, err
	}
	overlays := map[string]StrategyProfile{}
	if userID > 0 {
		userRows, _ := s.Repo.ListUserStrategyProfiles(ctx, userID)
		for _, u := range userRows {
			overlays[u.Code] = u
		}
	}
	active := ""
	if userID > 0 {
		active = s.Repo.GetBoundProfile(ctx, userID)
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, r := range rows {
		src := r
		accountOwned := false
		if o, ok := overlays[r.Code]; ok {
			src = o
			accountOwned = true
		}
		out = append(out, map[string]interface{}{
			"profileCode": r.Code, "profileName": src.Name,
			"config": parseJSONMap(src.ConfigJSON),
			"updateTime": formatNullableTime(src.UpdateTime),
			"accountOwned": accountOwned,
			"active": userID > 0 && r.Code == active,
		})
	}
	return out, nil
}

func (s *Service) SaveStrategyProfile(ctx context.Context, userID int, code, name string, config map[string]interface{}) error {
	_ = s.Repo.EnsureSeedProfiles(ctx)
	raw, _ := json.Marshal(config)
	if userID > 0 {
		return s.Repo.UpsertUserStrategyProfile(ctx, userID, code, name, string(raw))
	}
	return s.Repo.UpsertGlobalStrategyProfile(ctx, code, name, string(raw))
}

func (s *Service) BindStrategy(ctx context.Context, userID int, code string) (string, error) {
	code = strings.ToLower(strings.TrimSpace(code))
	if code != "conservative" && code != "balanced" && code != "aggressive" {
		return "", fmt.Errorf("策略档位无效，请选择 conservative / balanced / aggressive")
	}
	if err := s.Repo.BindUserStrategy(ctx, userID, code); err != nil {
		return "", err
	}
	return code, nil
}

func (s *Service) ResolveProfile(ctx context.Context, userID int, override string) string {
	return s.Repo.BoundProfile(ctx, userID, override)
}

func (s *Service) ListRiskRules(ctx context.Context) ([]map[string]interface{}, error) {
	_ = s.Repo.EnsureSeedProfiles(ctx)
	rows, err := s.Repo.ListRiskRules(ctx)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, r := range rows {
		out = append(out, map[string]interface{}{
			"ruleId": r.ID, "ruleName": r.Name, "ruleType": r.Type, "symbol": r.Symbol,
			"threshold": r.Threshold, "enabled": r.Enabled, "remark": r.Remark, "createTime": r.CreateTime,
		})
	}
	return out, nil
}

func (s *Service) SaveRiskRule(ctx context.Context, payload map[string]interface{}) (int64, error) {
	_ = s.Repo.EnsureSeedProfiles(ctx)
	name := str(payload["ruleName"])
	if name == "" {
		name = "规则"
	}
	typ := strOr(payload["ruleType"], "position")
	symbol := str(payload["symbol"])
	thr := num(payload["threshold"])
	enabled := strOr(payload["enabled"], "1")
	remark := str(payload["remark"])
	if id := intNum(payload["ruleId"]); id > 0 {
		if err := s.Repo.UpdateRiskRule(ctx, id, name, typ, symbol, thr, enabled, remark); err != nil {
			return 0, err
		}
		return int64(id), nil
	}
	return s.Repo.AddRiskRule(ctx, name, typ, symbol, thr, enabled, remark)
}

func (s *Service) DeleteRiskRule(ctx context.Context, id int) error {
	return s.Repo.DeleteRiskRule(ctx, id)
}

func (s *Service) ListRiskEvents(ctx context.Context, userID, limit int, status string) ([]map[string]interface{}, error) {
	if userID <= 0 {
		return []map[string]interface{}{}, nil
	}
	_, _ = s.Repo.ExpireOverdueRiskEvents(ctx, userID, 24)
	rows, err := s.Repo.ListRiskEvents(ctx, userID, limit, status)
	if err != nil {
		return []map[string]interface{}{}, nil
	}
	now := time.Now()
	out := make([]map[string]interface{}, 0, len(rows))
	for _, e := range rows {
		st := effectiveStatus(e.ReviewStatus, e.Handled, e.CreateTime, now)
		out = append(out, map[string]interface{}{
			"eventId": e.ID, "ruleId": nullableInt64(e.RuleID), "eventLevel": e.Level,
			"title": e.Title, "content": e.Content, "symbol": e.Symbol,
			"handled": handledFlag(st), "reviewStatus": st, "reviewStatusLabel": statusLabel(st),
			"handleRemark": nullableString(e.HandleRemark), "handledBy": nullableString(e.HandledBy),
			"handleTime": formatSQLTime(e.HandleTime), "createTime": e.CreateTime.Format("2006-01-02 15:04:05"),
		})
	}
	return out, nil
}

func (s *Service) EvaluateRisk(ctx context.Context, userID int) (map[string]interface{}, error) {
	if userID <= 0 {
		return map[string]interface{}{"created": 0, "rules": 0, "signalsChecked": 0, "message": "无法识别当前用户"}, nil
	}
	rules, err := s.ListRiskRules(ctx)
	if err != nil {
		return nil, err
	}
	enabled := filterEnabledRules(rules)
	signals, _ := s.Repo.ListRecentStrategySignals(ctx, userID, 30)
	created := 0
	for i, sig := range signals {
		if i >= 20 {
			break
		}
		for _, rule := range enabled {
			thr := num(rule["threshold"])
			if thr > 0 && thr <= 100 && sig.Score > 0 && sig.Score < math.Min(thr, 55) {
				rid := intNum(rule["ruleId"])
				var ruleID *int
				if rid > 0 {
					ruleID = &rid
				}
				if err := s.Repo.AddRiskEvent(ctx, userID, ruleID, "warn",
					fmt.Sprintf("%s · %s", rule["ruleName"], sig.Symbol),
					fmt.Sprintf("标的 %s 综合分 %.2f 触发规则阈值 %.0f（signal=%s）", sig.Symbol, sig.Score, thr, sig.Signal),
					sig.Symbol, "pending_review", "0"); err == nil {
					created++
				}
				break
			}
		}
	}
	if created > 0 {
		_ = s.Repo.AddNotification(ctx, userID, fmt.Sprintf("风控扫描产生 %d 条事件", created), "请查看风控事件列表", "warning", "risk")
	}
	return map[string]interface{}{"created": created, "rules": len(enabled), "signalsChecked": len(signals)}, nil
}

func (s *Service) UpdateRiskEventStatus(ctx context.Context, userID, eventID int, payload map[string]interface{}, operator string) (map[string]interface{}, error) {
	event, err := s.Repo.GetRiskEvent(ctx, userID, eventID)
	if err != nil {
		return nil, err
	}
	if event == nil {
		return nil, fmt.Errorf("风控事件不存在")
	}
	_, _ = s.Repo.ExpireOverdueRiskEvents(ctx, userID, 24)
	current := effectiveStatus(event.ReviewStatus, event.Handled, event.CreateTime, time.Now())
	target := str(payload["reviewStatus"])
	if target == "" {
		target = str(payload["status"])
	}
	if target == "" {
		if str(payload["handled"]) == "1" {
			target = "confirmed"
		} else if str(payload["handled"]) == "0" {
			target = "need_review"
		}
	}
	remark := str(payload["handleRemark"])
	if remark == "" {
		remark = str(payload["remark"])
	}
	change, err := applyStatusChange(current, target, remark, operator, time.Now())
	if err != nil {
		return nil, err
	}
	ok, err := s.Repo.UpdateRiskEventStatus(ctx, userID, eventID, change.Handled, change.ReviewStatus,
		change.HandleRemark, change.HandledBy, change.HandleTime)
	if err != nil {
		return nil, err
	}
	if !ok {
		return nil, fmt.Errorf("更新风控状态失败")
	}
	_ = s.Repo.AddNotification(ctx, userID, fmt.Sprintf("风控事件已%s", statusLabel(change.ReviewStatus)),
		fmt.Sprintf("事件 #%d %s · %s", eventID, event.Symbol, change.HandleRemark), "warning", "risk")
	return map[string]interface{}{
		"eventId": eventID, "reviewStatus": change.ReviewStatus,
		"reviewStatusLabel": statusLabel(change.ReviewStatus), "handled": change.Handled,
		"handleRemark": change.HandleRemark, "handledBy": change.HandledBy,
	}, nil
}

func (s *Service) HistoryCoverage(ctx context.Context) (map[string]interface{}, error) {
	instruments, err := s.Repo.ListCoverageInstruments(ctx)
	if err != nil {
		return nil, err
	}
	items := make([]map[string]interface{}, 0, len(instruments))
	covered := 0
	for _, inst := range instruments {
		latest := ""
		if s.Influx != nil {
			latest, _ = s.Influx.LatestDate(ctx, inst.Market, inst.Symbol)
		}
		ok := latest != ""
		if ok {
			covered++
		}
		items = append(items, map[string]interface{}{
			"symbol": inst.Symbol, "name": inst.Name, "market": inst.Market, "category": inst.Category,
			"latestDate": latest, "covered": ok, "status": map[bool]string{true: "ok", false: "missing"}[ok],
		})
	}
	total := len(items)
	pct := 0.0
	if total > 0 {
		pct = math.Round(float64(covered)/float64(total)*1000) / 10
	}
	return map[string]interface{}{
		"total": total, "covered": covered, "missing": total - covered,
		"coveragePct": pct, "items": items,
	}, nil
}

func (s *Service) ListAiTradeRuns(ctx context.Context, userID, limit int) ([]map[string]interface{}, error) {
	rows, err := s.Repo.ListAiTradeRuns(ctx, userID, limit)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, l := range rows {
		out = append(out, map[string]interface{}{
			"runId": l.RunID, "cycleId": l.CycleID, "userId": l.UserID, "source": l.Source,
			"strategyProfile": l.StrategyProfile, "targetCount": l.TargetCount,
			"evaluatedCount": l.EvaluatedCount, "opportunityCount": l.OpportunityCount,
			"submittedOrdersCount": l.SubmittedOrdersCount, "status": l.Status,
			"guardrailSnapshot": parseJSON(l.GuardrailSnapshot),
			"candidatesSnapshot": parseJSON(l.CandidatesSnapshot),
			"opportunitiesSnapshot": parseJSON(l.OpportunitiesSnapshot),
			"skippedReasons": parseJSON(l.SkippedReasons),
			"message": l.Message,
			"startedAt": formatSQLTime(l.StartedAt), "finishedAt": formatSQLTime(l.FinishedAt),
		})
	}
	return out, nil
}

func (s *Service) ListAutoDecisions(ctx context.Context, limit int, cycleID string) ([]map[string]interface{}, error) {
	rows, err := s.Repo.ListAutoDecisions(ctx, limit, cycleID)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, d := range rows {
		out = append(out, map[string]interface{}{
			"decisionId": d.DecisionID, "cycleId": d.CycleID, "symbol": d.Symbol, "market": d.Market,
			"side": d.Side, "quantity": d.Quantity, "price": nullableFloat64(d.Price),
			"confidence": nullableInt64(d.Confidence), "status": d.Status, "reason": nullableString(d.Reason),
			"source": d.Source, "orderId": nullableString(d.OrderID), "error": nullableString(d.Error),
			"createTime": d.CreateTime,
		})
	}
	return out, nil
}

func (s *Service) ListAiBatches(ctx context.Context) ([]map[string]interface{}, error) {
	rows, err := s.Repo.ListAiBatches(ctx, 20)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, b := range rows {
		out = append(out, map[string]interface{}{
			"batchId": b.ID, "cycleId": b.CycleID, "symbolsCount": b.SymbolsCount,
			"successCount": b.SuccessCount, "status": b.Status, "summary": b.Summary, "createTime": b.CreateTime,
		})
	}
	return out, nil
}

func (s *Service) ListAiBatchItems(ctx context.Context, batchID int) ([]map[string]interface{}, error) {
	rows, err := s.Repo.ListAiBatchItems(ctx, batchID)
	if err != nil {
		return nil, err
	}
	out := make([]map[string]interface{}, 0, len(rows))
	for _, it := range rows {
		out = append(out, map[string]interface{}{
			"itemId": it.ID, "symbol": it.Symbol, "market": it.Market,
			"decision": nullableString(it.Decision), "confidence": nullableInt64(it.Confidence),
			"summary": nullableString(it.Summary), "status": it.Status, "createTime": it.CreateTime,
		})
	}
	return out, nil
}

func (s *Service) SubmitAiBatch(ctx context.Context, symbols []string, market string, days int) (map[string]interface{}, error) {
	if s.Queue == nil {
		return nil, fmt.Errorf("队列不可用")
	}
	cycle := strings.ReplaceAll(uuid.NewString(), "-", "")[:16]
	if len(symbols) == 0 {
		instruments, _ := s.Repo.ListCoverageInstruments(ctx)
		for _, inst := range instruments {
			if inst.Market == market && !strings.HasPrefix(inst.Symbol, "^") {
				symbols = append(symbols, inst.Symbol)
				if len(symbols) >= 8 {
					break
				}
			}
		}
	}
	batchID, err := s.Repo.AddAiBatchRun(ctx, cycle, len(symbols), "任务执行中")
	if err != nil {
		return nil, err
	}
	ticket, err := s.Queue.Submit(ctx, "ai_batch", map[string]any{
		"batchId": batchID, "cycleId": cycle, "symbols": symbols, "market": market, "days": days,
	})
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"batchId": batchID, "cycleId": cycle, "jobId": ticket.JobID,
		"accepted": ticket.Accepted, "queue": ticket.Queue, "status": ticket.Status,
	}, nil
}

func (s *Service) GetFeishuConfig(ctx context.Context, userID int) (map[string]interface{}, error) {
	row, err := s.Repo.GetFeishuSub(ctx, userID)
	if err != nil {
		return nil, err
	}
	if row == nil {
		return map[string]interface{}{
			"personalEnabled": false, "groupEnabled": false,
			"personalWebhook": "", "groupWebhook": "",
			"pushTime": "18:30", "timezone": "Asia/Shanghai",
		}, nil
	}
	return serializeFeishu(row), nil
}

func (s *Service) SaveFeishuConfig(ctx context.Context, userID int, body map[string]interface{}) (map[string]interface{}, error) {
	pushTime := strings.TrimSpace(strOr(body["pushTime"], "18:30"))
	if len(pushTime) < 4 || !strings.Contains(pushTime, ":") {
		return nil, fmt.Errorf("推送时间格式应为 HH:MM")
	}
	row, err := s.Repo.UpsertFeishuSub(ctx, userID,
		flag(body["personalEnabled"]), flag(body["groupEnabled"]),
		str(body["personalWebhook"]), str(body["groupWebhook"]),
		pushTime[:8], strOr(body["timezone"], "Asia/Shanghai"))
	if err != nil {
		return nil, err
	}
	return serializeFeishu(row), nil
}

func (s *Service) TestFeishu(ctx context.Context, userID int, channel string) (map[string]interface{}, error) {
	row, err := s.Repo.GetFeishuSub(ctx, userID)
	if err != nil {
		return nil, err
	}
	if row == nil {
		return nil, fmt.Errorf("请先保存订阅配置")
	}
	webhook := ""
	if channel == "personal" {
		if row.PersonalWebhook.Valid {
			webhook = row.PersonalWebhook.String
		}
	} else if row.GroupWebhook.Valid {
		webhook = row.GroupWebhook.String
	}
	if webhook == "" {
		return nil, fmt.Errorf("该渠道未配置 Webhook")
	}
	payload := buildFeishuTestCard()
	ok, msg := postFeishu(webhook, payload)
	if !ok {
		return nil, fmt.Errorf("%s", msg)
	}
	return map[string]interface{}{"ok": true, "message": "测试卡片已发送"}, nil
}

func (s *Service) RiskTearsheet(ctx context.Context, userID int, days int) (map[string]interface{}, error) {
	window := days
	if window < 40 {
		window = 40
	}
	if window > 400 {
		window = 400
	}
	creds, err := s.Repo.LoadCreds(ctx, userID, s.CredentialKey, s.JWTSecret, s.AppEnv)
	if err != nil {
		return nil, err
	}
	if !creds.Configured() {
		return map[string]interface{}{
			"days": 0, "positions": 0, "message": "长桥凭据未配置",
		}, nil
	}
	positions, err := s.Broker.Positions(ctx, creds)
	if err != nil {
		return nil, err
	}
	if len(positions) == 0 {
		return map[string]interface{}{
			"days": 0, "positions": 0, "message": "当前没有持仓，无法计算组合指标",
		}, nil
	}
	quotes, _ := s.Broker.RealtimeQuotes(ctx, creds, collectSymbols(positions), "US")
	weights := map[string]float64{}
	markets := map[string]string{}
	names := map[string]string{}
	for i, pos := range positions {
		if i >= maxPositionsTearsheet {
			break
		}
		code, mkt := tradeexec.ParseSymbolMarket(pos.Symbol, "US")
		last := pos.LastPrice
		if last <= 0 {
			last = tradeexec.QuoteLastForSymbol(quotes, code, mkt, len(positions))
		}
		mv := pos.MarketValue
		if mv <= 0 {
			mv = pos.Quantity * last
		}
		if mv <= 0 {
			continue
		}
		weights[code] += mv
		markets[code] = mkt
		names[code] = pos.SymbolName
	}
	if len(weights) == 0 {
		return map[string]interface{}{
			"days": 0, "positions": len(positions), "message": "持仓缺少市值/价格，无法计算",
		}, nil
	}
	series := map[string][]float64{}
	for symbol, market := range markets {
		if s.Influx == nil {
			continue
		}
		bars, err := s.Influx.QueryKlines(ctx, market, symbol, fmt.Sprintf("-%dd", window+20), "now()", &window)
		if err != nil || len(bars) == 0 {
			continue
		}
		closes := make([]float64, 0, len(bars))
		for _, b := range bars {
			if b.Close != nil && *b.Close > 0 {
				closes = append(closes, *b.Close)
			}
		}
		rets := dailyReturns(closes)
		if len(rets) >= minReturns {
			if len(rets) > window {
				rets = rets[len(rets)-window:]
			}
			series[symbol] = rets
		}
	}
	port := weightedReturns(series, weights)
	metrics := computeMetrics(port)
	covered := make([]string, 0)
	for sym := range weights {
		if series[sym] != nil {
			covered = append(covered, sym)
		}
	}
	totalW := 0.0
	for _, sym := range covered {
		totalW += weights[sym]
	}
	wmap := map[string]float64{}
	nlist := make([]string, 0, len(covered))
	for _, sym := range covered {
		if totalW > 0 {
			wmap[sym] = math.Round(weights[sym]/totalW*10000) / 10000
		}
		nlist = append(nlist, names[sym])
	}
	msg := ""
	if len(covered) == 0 {
		msg = "持仓日 K 不足，无法计算组合指标"
	}
	return map[string]interface{}{
		"days": metrics["days"], "sharpe": metrics["sharpe"], "sortino": metrics["sortino"],
		"maxDrawdown": metrics["maxDrawdown"], "var95": metrics["var95"], "cvar95": metrics["cvar95"],
		"volatility": metrics["volatility"], "totalReturn": metrics["totalReturn"],
		"positions": len(weights), "covered": len(covered), "names": nlist, "weights": wmap, "message": msg,
	}, nil
}

func serializeFeishu(row *FeishuSub) map[string]interface{} {
	return map[string]interface{}{
		"subId": row.SubID, "userId": row.UserID,
		"personalEnabled": row.PersonalEnabled == "1", "groupEnabled": row.GroupEnabled == "1",
		"personalWebhook": nullableString(row.PersonalWebhook), "groupWebhook": nullableString(row.GroupWebhook),
		"pushTime": row.PushTime, "timezone": row.Timezone,
		"lastPersonalKey": nullableString(row.LastPersonalKey), "lastGroupKey": nullableString(row.LastGroupKey),
		"lastError": nullableString(row.LastError),
	}
}

func buildFeishuTestCard() map[string]interface{} {
	return map[string]interface{}{
		"msg_type": "interactive",
		"card": map[string]interface{}{
			"header": map[string]interface{}{
				"title": map[string]interface{}{"tag": "plain_text", "content": "次日策略摘要"},
				"template": "blue",
			},
			"elements": []interface{}{
				map[string]interface{}{
					"tag": "div",
					"text": map[string]interface{}{
						"tag": "lark_md", "content": "这是一条测试卡片，正式推送会带上当日策略标的。",
					},
				},
			},
		},
	}
}

func postFeishu(webhook string, payload map[string]interface{}) (bool, string) {
	raw, _ := json.Marshal(payload)
	resp, err := http.Post(webhook, "application/json", bytes.NewReader(raw))
	if err != nil {
		return false, err.Error()
	}
	defer resp.Body.Close()
	var data map[string]interface{}
	_ = json.NewDecoder(resp.Body).Decode(&data)
	if resp.StatusCode >= 400 {
		return false, fmt.Sprintf("HTTP %d", resp.StatusCode)
	}
	if code, ok := data["code"].(float64); ok && int(code) != 0 {
		return false, str(data["msg"])
	}
	return true, "ok"
}

func dailyReturns(closes []float64) []float64 {
	out := make([]float64, 0, len(closes))
	var prev float64
	for _, px := range closes {
		if prev > 0 && px > 0 {
			out = append(out, px/prev-1)
		}
		if px > 0 {
			prev = px
		}
	}
	return out
}

func computeMetrics(rets []float64) map[string]interface{} {
	n := len(rets)
	if n < minReturns {
		return map[string]interface{}{
			"days": n, "sharpe": nil, "sortino": nil, "maxDrawdown": nil,
			"var95": nil, "cvar95": nil, "volatility": nil, "totalReturn": nil,
		}
	}
	mean := 0.0
	for _, r := range rets {
		mean += r
	}
	mean /= float64(n)
	variance := 0.0
	for _, r := range rets {
		variance += (r - mean) * (r - mean)
	}
	variance /= float64(n)
	sigma := math.Sqrt(variance)
	down := make([]float64, 0)
	for _, r := range rets {
		if r < 0 {
			down = append(down, r)
		}
	}
	downVar := 0.0
	for _, r := range down {
		downVar += r * r
	}
	if len(down) > 0 {
		downVar /= float64(len(down))
	}
	downSigma := math.Sqrt(downVar)
	ordered := append([]float64{}, rets...)
	for i := 0; i < len(ordered); i++ {
		for j := i + 1; j < len(ordered); j++ {
			if ordered[j] < ordered[i] {
				ordered[i], ordered[j] = ordered[j], ordered[i]
			}
		}
	}
	idx := int(float64(n) * 0.05)
	if idx >= n {
		idx = n - 1
	}
	if idx < 0 {
		idx = 0
	}
	var95 := ordered[idx]
	tail := ordered[:idx+1]
	cvar := var95
	if len(tail) > 0 {
		sum := 0.0
		for _, v := range tail {
			sum += v
		}
		cvar = sum / float64(len(tail))
	}
	total := 1.0
	for _, r := range rets {
		total *= 1 + r
	}
	sharpe := interface{}(nil)
	sortino := interface{}(nil)
	if sigma > 0 {
		sharpe = math.Round(mean/sigma*math.Sqrt(float64(tradingDays))*10000) / 10000
	}
	if downSigma > 0 {
		sortino = math.Round(mean/downSigma*math.Sqrt(float64(tradingDays))*10000) / 10000
	}
	return map[string]interface{}{
		"days": n, "sharpe": sharpe, "sortino": sortino,
		"maxDrawdown": math.Round(maxDrawdown(rets)*10000) / 10000,
		"var95": math.Round(var95*1e6) / 1e6, "cvar95": math.Round(cvar*1e6) / 1e6,
		"volatility": math.Round(sigma*math.Sqrt(float64(tradingDays))*10000) / 10000,
		"totalReturn": math.Round((total-1)*10000) / 10000,
	}
}

func maxDrawdown(rets []float64) float64 {
	equity := 1.0
	peak := 1.0
	worst := 0.0
	for _, ret := range rets {
		equity *= 1 + ret
		if equity > peak {
			peak = equity
		}
		if peak > 0 {
			dd := equity/peak - 1
			if dd < worst {
				worst = dd
			}
		}
	}
	return worst
}

func weightedReturns(series map[string][]float64, weights map[string]float64) []float64 {
	if len(series) == 0 {
		return nil
	}
	length := len(series)
	for _, vals := range series {
		if len(vals) < length {
			length = len(vals)
		}
	}
	if length < minReturns {
		return nil
	}
	totalW := 0.0
	for sym := range series {
		totalW += weights[sym]
	}
	if totalW <= 0 {
		return nil
	}
	out := make([]float64, 0, length)
	for i := 0; i < length; i++ {
		acc := 0.0
		for sym, vals := range series {
			w := weights[sym]
			if w <= 0 || i >= len(vals) {
				continue
			}
			acc += (w / totalW) * vals[i]
		}
		out = append(out, acc)
	}
	return out
}

func collectSymbols(positions []tradeexec.Position) []string {
	out := make([]string, 0, len(positions))
	for _, p := range positions {
		if p.Symbol != "" {
			out = append(out, p.Symbol)
		}
	}
	return out
}

func filterEnabledRules(rules []map[string]interface{}) []map[string]interface{} {
	out := make([]map[string]interface{}, 0)
	for _, r := range rules {
		if fmt.Sprint(r["enabled"]) == "1" {
			out = append(out, r)
		}
	}
	return out
}

func trimEquity(points []backtest.EquityPoint, n int) []backtest.EquityPoint {
	if len(points) <= n {
		return points
	}
	return points[len(points)-n:]
}

func normalizeProfile(code string) string {
	c := strings.ToLower(strings.TrimSpace(code))
	if c == "conservative" || c == "balanced" || c == "aggressive" {
		return c
	}
	return "balanced"
}

func parseJSONMap(raw string) map[string]interface{} {
	var out map[string]interface{}
	_ = json.Unmarshal([]byte(raw), &out)
	if out == nil {
		return map[string]interface{}{}
	}
	return out
}

func parseJSON(raw string) interface{} {
	if strings.TrimSpace(raw) == "" {
		return map[string]interface{}{}
	}
	var out interface{}
	if err := json.Unmarshal([]byte(raw), &out); err != nil {
		return []interface{}{}
	}
	return out
}

func str(v interface{}) string {
	if v == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(v))
}

func strOr(v interface{}, fallback string) string {
	s := str(v)
	if s == "" {
		return fallback
	}
	return s
}

func num(v interface{}) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case int:
		return float64(x)
	case int64:
		return float64(x)
	default:
		return 0
	}
}

func intNum(v interface{}) int {
	return int(num(v))
}

func flag(v interface{}) string {
	switch x := v.(type) {
	case bool:
		if x {
			return "1"
		}
	case string:
		if strings.EqualFold(x, "true") || x == "1" {
			return "1"
		}
	case float64:
		if x != 0 {
			return "1"
		}
	}
	return "0"
}

func nullableString(v sql.NullString) interface{} {
	if v.Valid {
		return v.String
	}
	return nil
}

func nullableInt64(v sql.NullInt64) interface{} {
	if v.Valid {
		return v.Int64
	}
	return nil
}

func nullableFloat64(v sql.NullFloat64) interface{} {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func formatSQLTime(v sql.NullTime) interface{} {
	if v.Valid {
		return v.Time.Format("2006-01-02 15:04:05")
	}
	return nil
}

func formatNullableTime(t sql.NullTime) string {
	if t.Valid {
		return t.Time.Format("2006-01-02 15:04:05")
	}
	return ""
}
