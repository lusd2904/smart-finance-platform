package handlers

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/factor"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/indicators"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/longbridge"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/store"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/kline"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/response"
)

const stopLossPct = -8.0

func (s *Server) MarketIndicators(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	symbol := strings.ToUpper(strings.TrimSpace(q.Get("symbol")))
	market := strings.ToUpper(defaultStr(q.Get("market"), "US"))
	start := defaultStr(q.Get("start"), "-2y")
	stop := defaultStr(q.Get("stop"), "now()")
	if symbol == "" {
		response.Error(w, "symbol 不能为空")
		return
	}
	limit := 800
	bars, err := s.Influx.GetKlineSeries(r.Context(), market, symbol, "daily", start, stop, &limit)
	if err != nil || len(bars) == 0 {
		response.Error(w, "K线数据不足，无法计算指标")
		return
	}
	series := indicators.Calculate(influxBarsToIndicator(bars))
	series["symbol"] = symbol
	series["market"] = market
	Success(w, series)
}

func (s *Server) MarketAIAnalyzeStream(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	symbol := strings.ToUpper(strings.TrimSpace(q.Get("symbol")))
	market := strings.ToUpper(defaultStr(q.Get("market"), "US"))
	if symbol == "" {
		response.Error(w, "symbol 不能为空")
		return
	}
	w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	flusher, ok := w.(http.Flusher)
	if !ok {
		response.Error(w, "streaming unsupported")
		return
	}
	writeSSE := func(text string) {
		_, _ = w.Write([]byte(text))
		flusher.Flush()
	}
	writeSSE("正在加载 K 线与市场环境…\n")
	ticket, err := s.Queue.Submit(r.Context(), "ai_analyze", map[string]interface{}{
		"symbol": symbol, "market": market, "days": intQuery(q.Get("days"), 90),
	})
	if err != nil || ticket == nil {
		writeSSE(jsonError("分析任务入队失败"))
		return
	}
	deadline := time.Now().Add(90 * time.Second)
	jobID := fmt.Sprint(ticket["jobId"])
	for time.Now().Before(deadline) {
		t, _ := s.Queue.GetTicket(r.Context(), jobID)
		if t != nil {
			status := strings.ToLower(fmt.Sprint(t["status"]))
			if status == "failed" || status == "error" {
				writeSSE(jsonError(fmt.Sprint(t["message"])))
				return
			}
			if status == "done" || status == "success" || status == "completed" {
				break
			}
			if msg := fmt.Sprint(t["message"]); msg != "" && msg != "<nil>" {
				writeSSE(msg + "\n")
			}
		}
		time.Sleep(800 * time.Millisecond)
	}
	data, err := s.DB.LatestAIAnalysis(r.Context(), symbol, market)
	if err != nil || data == nil {
		writeSSE(jsonError("分析结果暂不可用，请稍后重试"))
		return
	}
	sections := []struct{ title, body string }{
		{"建议", fmt.Sprintf("%v · %v · 置信度 %v", data["recommendation"], data["stance"], data["confidence"])},
		{"综合", fmt.Sprint(data["summary"])},
		{"指标", fmt.Sprint(data["indicatorReview"])},
		{"舆情", fmt.Sprint(data["sentimentReview"])},
		{"操作", fmt.Sprint(data["operationAdvice"])},
		{"风险", fmt.Sprint(data["riskWarning"])},
	}
	for _, sec := range sections {
		if strings.TrimSpace(sec.body) != "" && sec.body != "<nil>" {
			writeSSE(fmt.Sprintf("\n【%s】\n%s\n", sec.title, sec.body))
		}
	}
	writeSSE("\n[完成]\n")
}

func (s *Server) SymbolContent(w http.ResponseWriter, r *http.Request) {
	symbol := pathParam(r.URL.Path, "/market/symbols/", "/content")
	q := r.URL.Query()
	market := defaultStr(q.Get("market"), "US")
	contentType := defaultStr(q.Get("type"), "news")
	limit := intQuery(q.Get("limit"), 20)
	refresh := strings.EqualFold(q.Get("refresh"), "true") || q.Get("refresh") == "1"
	data, err := s.DB.GetSymbolContent(r.Context(), symbol, market, contentType, limit, refresh)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	Success(w, data)
}

func (s *Server) FactorCompute(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	symbol := strings.ToUpper(strings.TrimSpace(q.Get("symbol")))
	market := strings.ToUpper(defaultStr(q.Get("market"), "US"))
	profile := defaultStr(q.Get("profile"), "balanced")
	if symbol == "" {
		response.Error(w, "symbol 不能为空")
		return
	}
	limit := 260
	bars, err := s.Influx.GetKlineSeries(r.Context(), market, symbol, "daily", "-2y", "now()", &limit)
	if err != nil || len(bars) < 20 {
		Success(w, map[string]interface{}{"ok": false, "reason": "K线数据不足，无法计算因子"})
		return
	}
	fbars := influxBarsToFactor(bars)
	metrics := factor.ComputeMetrics(fbars)
	if !metrics.OK {
		Success(w, map[string]interface{}{"ok": false, "reason": metrics.Reason})
		return
	}
	score := factor.ScoreMetrics(metrics, profile, factor.MergeWeights(profile, nil))
	Success(w, map[string]interface{}{
		"ok": true, "symbol": symbol, "market": market,
		"metrics": metrics.Values, "score": score,
		"alphaCs": metrics.Alpha101,
	})
}

func (s *Server) ScanIndicators(w http.ResponseWriter, r *http.Request) {
	data, err := s.DB.RunIndicatorRefresh(r.Context(), s.queryLatestKlineMap)
	if err != nil {
		response.Error(w, "指标快照刷新失败")
		return
	}
	Success(w, data)
}

func (s *Server) ScanPositions(w http.ResponseWriter, r *http.Request) {
	data, err := s.runPositionMonitor(r.Context())
	if err != nil {
		response.Error(w, "持仓监控失败")
		return
	}
	Success(w, data)
}

func (s *Server) LongbridgeConfigGet(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	cfg, err := s.DB.GetLongbridgeConfig(r.Context(), userID, credKey, jwtSecret, appEnv)
	if err != nil {
		response.Error(w, "长桥配置查询失败")
		return
	}
	Success(w, s.DB.ToConfigModel(cfg))
}

func (s *Server) LongbridgeConfigPut(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	body, err := readJSONBody(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	cfg := store.LongbridgeConfig{
		UserID:               userID,
		AppKey:               fmt.Sprint(body["appKey"]),
		AppSecret:            fmt.Sprint(body["appSecret"]),
		AccessToken:          fmt.Sprint(body["accessToken"]),
		Region:               fmt.Sprint(body["region"]),
		AutoTradeEnabled:     body["autoTradeEnabled"] == true,
		DailyBuyRatio:        floatOr(body["dailyBuyRatio"], 0.20),
		MaxSymbolPositionPct: floatOr(body["maxSymbolPositionPct"], 0.10),
	}
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	if err := s.DB.SaveLongbridgeConfig(r.Context(), userID, cfg, credKey, jwtSecret, appEnv); err != nil {
		response.Error(w, "保存失败")
		return
	}
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: "保存成功", Success: true, Time: time.Now().Format(time.RFC3339)})
}

func (s *Server) LongbridgeTest(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	creds, err := s.DB.LoadLongbridgeCreds(r.Context(), userID, credKey, jwtSecret, appEnv)
	if err != nil {
		response.Error(w, "凭据读取失败")
		return
	}
	if !creds.Configured() {
		Success(w, map[string]interface{}{"configured": false, "connected": false, "message": "长桥凭据未配置"})
		return
	}
	broker := s.broker()
	acct, err := broker.AccountBalance(r.Context(), creds)
	if err != nil || !acct.Configured {
		Success(w, map[string]interface{}{
			"configured": true, "connected": false, "region": creds.Region,
			"message": firstNonEmpty(acct.Message, "连通性测试失败"),
		})
		return
	}
	Success(w, map[string]interface{}{
		"configured": true, "connected": true, "source": creds.Source, "region": creds.Region,
		"message": "长桥连接正常",
	})
}

func (s *Server) DailyListOpen(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	body, err := readJSONBody(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	itemIDs := parseIDList(body["itemIds"], body["ids"])
	if len(itemIDs) == 0 {
		response.Error(w, "请先勾选标的，禁止整表默认全开")
		return
	}
	listID, _, err := s.DB.LatestOpenDailyListID(r.Context(), userID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	ready, reason := s.DB.AccountTradeReady(r.Context(), userID)
	if !ready {
		response.Error(w, reason)
		return
	}
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	creds, _ := s.DB.LoadLongbridgeCreds(r.Context(), userID, credKey, jwtSecret, appEnv)
	broker := s.broker()
	autoJoin := body["autoJoin"] == true
	outcomes := []map[string]interface{}{}
	for _, itemID := range itemIDs {
		item, err := s.DB.GetDailyListItem(r.Context(), itemID, userID)
		if err != nil || fmt.Sprint(item["listId"]) != fmt.Sprint(listID) {
			outcomes = append(outcomes, map[string]interface{}{"itemId": itemID, "ok": false, "message": "条目不属于当前清单"})
			continue
		}
		if autoJoin {
			_ = s.DB.AddQuantWatchlistSymbol(r.Context(), userID, fmt.Sprint(item["symbol"]), fmt.Sprint(item["market"]), "次日清单自动交易")
		}
		out := s.placeDailyListOrder(r.Context(), broker, creds, item)
		outcomes = append(outcomes, out)
	}
	if autoJoin {
		_ = s.DB.UpdateDailyListAuto(r.Context(), listID, true)
	}
	list, _ := s.DB.DailyListLatest(r.Context(), userID)
	SuccessMsg(w, "已提交勾选标的", map[string]interface{}{"list": list["list"], "outcomes": outcomes})
}

func (s *Server) DailyListAuto(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	body, err := readJSONBody(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	enabled := true
	if v, ok := body["enabled"]; ok {
		enabled = v == true
	}
	list, err := s.DB.DailyListLatest(r.Context(), userID)
	if err != nil || list["empty"] == true {
		response.Error(w, "暂无清单")
		return
	}
	listMap, _ := list["list"].(map[string]interface{})
	listID, _ := listMap["listId"].(int64)
	if enabled {
		ready, reason := s.DB.AccountTradeReady(r.Context(), userID)
		if !ready {
			response.Error(w, reason)
			return
		}
	}
	itemIDs := parseIDList(body["itemIds"])
	_ = s.DB.UpdateDailyListAuto(r.Context(), listID, enabled)
	_ = s.DB.SetDailyListItemAuto(r.Context(), listID, itemIDs, enabled)
	if enabled {
		for _, id := range itemIDs {
			item, err := s.DB.GetDailyListItem(r.Context(), id, userID)
			if err == nil {
				_ = s.DB.AddQuantWatchlistSymbol(r.Context(), userID, fmt.Sprint(item["symbol"]), fmt.Sprint(item["market"]), "次日清单自动交易")
			}
		}
	}
	updated, _ := s.DB.DailyListLatest(r.Context(), userID)
	Success(w, updated["list"])
}

func (s *Server) broker() *tradeexec.SDKBroker {
	if s.Broker != nil {
		return s.Broker
	}
	return tradeexec.NewSDKBroker()
}

func (s *Server) placeDailyListOrder(ctx context.Context, broker *tradeexec.SDKBroker, creds tradeexec.Creds, item map[string]interface{}) map[string]interface{} {
	itemIDVal, _ := toFloat64(item["itemId"])
	itemIDInt := int64(itemIDVal)
	symbol := fmt.Sprint(item["symbol"])
	market := fmt.Sprint(item["market"])
	status := fmt.Sprint(item["status"])
	if status == "submitted" || status == "filled" {
		return map[string]interface{}{"itemId": itemIDInt, "ok": true, "idempotent": true, "message": "当日已下单", "orderId": item["orderId"]}
	}
	if status == "skipped" {
		return map[string]interface{}{"itemId": itemIDInt, "ok": false, "message": item["error"]}
	}
	acct, _ := broker.AccountBalance(ctx, creds)
	price, _ := toFloat64(item["price"])
	qty := tradeexec.SizeDailyListOrder(acct, market, price, 0)
	if qty <= 0 {
		_ = s.DB.UpdateDailyListItem(ctx, itemIDInt, "skipped", "", "仓位不足或无法计算数量", 0)
		return map[string]interface{}{"itemId": itemIDInt, "ok": false, "message": "仓位不足或无法计算数量"}
	}
	res := broker.SubmitOrder(ctx, creds, tradeexec.SubmitReq{
		Symbol: symbol, Side: "BUY", Quantity: float64(qty), OrderType: "MO", Market: market,
	})
	st := "rejected"
	if res.OK {
		st = "submitted"
	}
	_ = s.DB.UpdateDailyListItem(ctx, itemIDInt, st, res.OrderID, res.Message, qty)
	return map[string]interface{}{"itemId": itemIDInt, "ok": res.OK, "message": res.Message, "orderId": res.OrderID}
}

func (s *Server) runPositionMonitor(ctx context.Context) (map[string]interface{}, error) {
	userIDs, err := s.DB.ListConfiguredLongbridgeUsers(ctx)
	if err != nil {
		return nil, err
	}
	if len(userIDs) == 0 {
		return map[string]interface{}{
			"configured": false, "count": 0, "alertCount": 0, "soldCount": 0,
			"alerts": []interface{}{}, "asOf": time.Now().Format("2006-01-02 15:04:05"),
		}, nil
	}
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	broker := s.broker()
	alerts := []map[string]interface{}{}
	sold := 0
	positionCount := 0
	for _, uid := range userIDs {
		creds, err := s.DB.LoadLongbridgeCreds(ctx, uid, credKey, jwtSecret, appEnv)
		if err != nil || !creds.Configured() {
			continue
		}
		settings := s.DB.LoadTradeSettings(ctx, uid)
		positions, err := broker.Positions(ctx, creds)
		if err != nil {
			continue
		}
		positionCount += len(positions)
		for _, pos := range positions {
			symbol, market := tradeexec.ParseSymbolMarket(pos.Symbol, "US")
			qty := tradeexec.PositionQuantity(&pos)
			cost, last := pos.CostPrice, pos.LastPrice
			if last <= 0 {
				quotes, _ := broker.RealtimeQuotes(ctx, creds, []string{symbol}, market)
				last = tradeexec.ExtractLastPrice(quotes, longbridge.ToSymbol(symbol, market))
			}
			if cost <= 0 || last <= 0 {
				continue
			}
			pnlPct := (last - cost) / cost * 100
			if pnlPct > stopLossPct {
				continue
			}
			alert := map[string]interface{}{
				"userId": uid, "symbol": symbol, "market": market, "quantity": qty,
				"costPrice": cost, "lastPrice": last, "pnlPct": round4(pnlPct), "level": "danger",
				"title": fmt.Sprintf("持仓止损 · %s", symbol),
				"content": fmt.Sprintf("用户%d %s 现价 %.4f 相对成本 %.4f 浮亏 %.4f%%", uid, symbol, last, cost, pnlPct),
			}
			if settings.AutoTradeEnabled && qty > 0 {
				res := broker.SubmitOrder(ctx, creds, tradeexec.SubmitReq{
					Symbol: symbol, Side: "SELL", Quantity: float64(int(qty)), OrderType: "MO", Market: market,
				})
				if res.OK {
					sold++
					alert["content"] = fmt.Sprint(alert["content"]) + "；已按市价卖出"
				} else {
					alert["content"] = fmt.Sprint(alert["content"]) + "；下单失败 " + res.Message
				}
			}
			alerts = append(alerts, alert)
		}
	}
	return map[string]interface{}{
		"configured": true, "count": positionCount, "alertCount": len(alerts), "soldCount": sold,
		"alerts": alerts, "asOf": time.Now().Format("2006-01-02 15:04:05"),
	}, nil
}

func (s *Server) queryLatestKlineMap(ctx context.Context, market string, symbols []string, limit int) (map[string][]map[string]interface{}, error) {
	out := map[string][]map[string]interface{}{}
	for _, symbol := range symbols {
		lim := limit
		bars, err := s.Influx.GetKlineSeries(ctx, market, symbol, "daily", "-90d", "now()", &lim)
		if err != nil {
			return nil, err
		}
		rows := []map[string]interface{}{}
		for _, b := range bars {
			rows = append(rows, map[string]interface{}{
				"date": b.Date, "close": ptrVal(b.Close), "volume": ptrVal(b.Volume),
			})
		}
		out[symbol] = rows
	}
	return out, nil
}

func influxBarsToIndicator(bars []kline.Bar) []indicators.Bar {
	out := make([]indicators.Bar, 0, len(bars))
	for _, b := range bars {
		out = append(out, indicators.Bar{
			Date: b.Date, Open: ptrVal(b.Open), High: ptrVal(b.High),
			Low: ptrVal(b.Low), Close: ptrVal(b.Close), Volume: ptrVal(b.Volume),
		})
	}
	return out
}

func influxBarsToFactor(bars []kline.Bar) []factor.Bar {
	out := make([]factor.Bar, 0, len(bars))
	for _, b := range bars {
		out = append(out, factor.Bar{
			Date: b.Date, Open: ptrVal(b.Open), High: ptrVal(b.High),
			Low: ptrVal(b.Low), Close: ptrVal(b.Close), Volume: ptrVal(b.Volume),
		})
	}
	return out
}

func ptrVal(p *float64) float64 {
	if p == nil {
		return 0
	}
	return *p
}

func parseIDList(a interface{}, b ...interface{}) []int64 {
	raw := a
	if raw == nil && len(b) > 0 {
		raw = b[0]
	}
	var ids []int64
	switch xs := raw.(type) {
	case []interface{}:
		for _, v := range xs {
			if id, err := strconv.ParseInt(fmt.Sprint(v), 10, 64); err == nil {
				ids = append(ids, id)
			}
		}
	case []int:
		for _, v := range xs {
			ids = append(ids, int64(v))
		}
	}
	return ids
}

func floatOr(v interface{}, def float64) float64 {
	switch x := v.(type) {
	case float64:
		return x
	case int:
		return float64(x)
	case json.Number:
		f, _ := x.Float64()
		return f
	default:
		return def
	}
}

func jsonError(msg string) string {
	b, _ := json.Marshal(map[string]string{"error": msg})
	return string(b)
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if strings.TrimSpace(v) != "" {
			return v
		}
	}
	return ""
}

func toFloat64(v interface{}) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case float32:
		return float64(x), true
	case int:
		return float64(x), true
	case int64:
		return float64(x), true
	default:
		return 0, false
	}
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}
