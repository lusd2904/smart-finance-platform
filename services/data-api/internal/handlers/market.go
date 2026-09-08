package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/kline"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/response"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/timeutil"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/store"
)

func (s *Server) InstrumentList(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	items, err := s.DB.ListInstruments(r.Context(), store.InstrumentQuery{
		Market: q.Get("market"), Category: q.Get("category"), Enabled: q.Get("enabled"), Keyword: q.Get("keyword"),
	})
	if err != nil {
		response.Error(w, "标的列表查询失败")
		return
	}
	Success(w, items)
}

func (s *Server) InstrumentUniverse(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	page, counts, err := s.DB.InstrumentUniverse(r.Context(), q.Get("market"), q.Get("enabled"), q.Get("keyword"),
		intQuery(q.Get("pageNum"), 1), intQuery(q.Get("pageSize"), 20))
	if err != nil {
		response.Error(w, "全市场标的查询失败")
		return
	}
	SuccessPageExtra(w, page, map[string]interface{}{"counts": counts})
}

func (s *Server) FinanceBriefings(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	limit := intQuery(q.Get("limit"), 20)
	items, err := s.DB.ListFinanceBriefings(r.Context(), q.Get("market"), q.Get("symbol"), limit)
	if err != nil {
		SuccessMsg(w, "财经资讯源暂时不可用，已返回空列表，请稍后重试", map[string]interface{}{
			"success": true, "data": []interface{}{},
			"message": "财经资讯源暂时不可用，已返回空列表，请稍后重试",
			"meta":    map[string]interface{}{"count": 0, "market": q.Get("market")},
		})
		return
	}
	data := map[string]interface{}{
		"success": true, "data": items,
		"meta": map[string]interface{}{"count": len(items), "market": q.Get("market")},
	}
	Success(w, data)
}

func (s *Server) ReviewLatest(w http.ResponseWriter, r *http.Request) {
	items, err := s.DB.ListReviewLatest(r.Context())
	if err != nil {
		response.Error(w, "收盘分析查询失败")
		return
	}
	Success(w, map[string]interface{}{
		"items": items, "count": len(items), "aiAvailable": true, "aiHint": nil,
	})
}

func (s *Server) ReviewHistory(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	items, err := s.DB.ListReviewHistory(r.Context(), q.Get("market"), intQuery(q.Get("limit"), 60))
	if err != nil {
		response.Error(w, "收盘分析历史查询失败")
		return
	}
	Success(w, map[string]interface{}{"items": items, "count": len(items)})
}

func (s *Server) StockPickMood(w http.ResponseWriter, r *http.Request) {
	data, err := s.DB.StockPickMood(r.Context())
	if err != nil {
		response.Error(w, "舆情情绪查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) StockPickDates(w http.ResponseWriter, r *http.Request) {
	data, err := s.DB.StockPickDates(r.Context(), intQuery(r.URL.Query().Get("limit"), 60))
	if err != nil {
		response.Error(w, "选股日期查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) StockPickLatest(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	data, err := s.DB.StockPickLatest(r.Context(), q.Get("market"), q.Get("tradeDate"))
	if err != nil {
		response.Error(w, "选股单查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) WatchlistOverview(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	enabled, err := s.DB.WatchlistEnabled(r.Context(), userID)
	if err != nil {
		response.Error(w, "自选总览查询失败")
		return
	}
	rows := []map[string]interface{}{}
	stanceCount := map[string]int{"偏多": 0, "偏空": 0, "中性": 0}
	var lastTime interface{}
	for _, row := range enabled {
		symbol := fmt.Sprint(row["symbol"])
		market := fmt.Sprint(row["market"])
		analysis, _ := s.DB.LatestWatchlistAnalysis(r.Context(), userID, symbol, market)
		if analysis != nil {
			if st, ok := analysis["stance"].(string); ok {
				stanceCount[st]++
			}
			if analysis["analysisTime"] != nil {
				lastTime = analysis["analysisTime"]
			}
		}
		item := map[string]interface{}{
			"id": row["id"], "userId": row["userId"], "symbol": symbol, "market": market,
			"name": row["name"], "note": row["note"], "enabled": row["enabled"],
			"sortOrder": row["sortOrder"], "createTime": row["createTime"],
			"analysis": analysis, "quoteSource": "mysql",
		}
		if analysis != nil {
			item["recommendation"] = analysis["recommendation"]
			item["stance"] = analysis["stance"]
			item["confidence"] = analysis["confidence"]
			item["summary"] = analysis["summary"]
			item["analysisTime"] = analysis["analysisTime"]
			item["source"] = analysis["source"]
		}
		rows = append(rows, item)
	}
	Success(w, map[string]interface{}{
		"count": len(rows), "bullish": stanceCount["偏多"], "bearish": stanceCount["偏空"],
		"neutral": stanceCount["中性"], "lastAnalysisTime": lastTime, "quoteSource": "mysql",
		"aiAvailable": true, "aiModel": nil, "aiHint": nil, "groups": []interface{}{}, "items": rows,
	})
}

func (s *Server) WatchlistList(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	q := r.URL.Query()
	page, err := s.DB.WatchlistPage(r.Context(), userID, q.Get("symbol"), q.Get("market"), q.Get("enabled"),
		intQuery(q.Get("pageNum"), 1), intQuery(q.Get("pageSize"), 10))
	if err != nil {
		response.Error(w, "自选列表查询失败")
		return
	}
	SuccessPage(w, page)
}

func (s *Server) WatchlistAdd(w http.ResponseWriter, r *http.Request) {
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
	if err := s.DB.AddWatchlist(r.Context(), userID, fmt.Sprint(body["symbol"]), fmt.Sprint(body["market"]),
		fmt.Sprint(body["name"]), fmt.Sprint(body["note"])); err != nil {
		response.Error(w, "新增自选失败")
		return
	}
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: "新增成功", Success: true, Time: timeutil.NowBeijingRFC()})
}

func (s *Server) WatchlistDelete(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	idsRaw := strings.TrimPrefix(r.URL.Path, "/market/watchlist/")
	ids := parseIDs(idsRaw)
	if _, err := s.DB.DeleteWatchlist(r.Context(), userID, ids); err != nil {
		response.Error(w, "删除自选失败")
		return
	}
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: "删除成功", Success: true, Time: timeutil.NowBeijingRFC()})
}

func (s *Server) WatchlistAnalysis(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	q := r.URL.Query()
	items, err := s.DB.WatchlistAnalysisHistory(r.Context(), userID, q.Get("symbol"),
		defaultStr(q.Get("market"), "US"), intQuery(q.Get("limit"), 24))
	if err != nil {
		response.Error(w, "分析历史查询失败")
		return
	}
	Success(w, items)
}

func (s *Server) WatchlistBacktest(w http.ResponseWriter, r *http.Request) {
	SuccessMsg(w, "回测完成（Go 简化版：完整回测需 legacy Python）", map[string]interface{}{
		"message": "Go data-api 简化回测：请使用 legacy Python 获取完整前瞻收益统计",
		"items":   []interface{}{}, "hitRate": nil,
	})
}

func (s *Server) WatchlistCorrelation(w http.ResponseWriter, r *http.Request) {
	SuccessMsg(w, "操作成功", map[string]interface{}{
		"message": "Go data-api 简化相关矩阵：完整 Pearson 相关需 Influx 批量查询",
		"symbols": []interface{}{}, "matrix": []interface{}{},
	})
}

func (s *Server) SymbolOverview(w http.ResponseWriter, r *http.Request) {
	symbol := pathParam(r.URL.Path, "/market/symbols/", "/overview")
	q := r.URL.Query()
	market := defaultStr(q.Get("market"), "US")
	include := strings.ToLower(defaultStr(q.Get("include"), "core"))
	limit := intQuery(q.Get("historyLimit"), 120)
	instrument, _ := s.DB.GetInstrumentBySymbol(r.Context(), symbol)
	name := symbol
	if instrument != nil && instrument["name"] != nil {
		name = fmt.Sprint(instrument["name"])
	}
	bars, _ := s.Influx.GetKlineSeries(r.Context(), market, symbol, "daily", "-1y", "now()", &limit)
	quote := quoteFromBars(bars)
	latestAI, _ := s.DB.LatestAIAnalysis(r.Context(), symbol, market)
	core := map[string]interface{}{
		"symbol": symbol, "market": market, "name": name,
		"fundamentals": map[string]interface{}{"symbol": symbol, "name": name, "market": market},
		"quote":        quote,
		"techSnapshot": map[string]interface{}{},
		"latestAiAnalysis": latestAI,
		"latestTrendScan":  nil,
		"meta": map[string]interface{}{"include": "core", "priceSource": "history"},
	}
	if include != "all" {
		Success(w, core)
		return
	}
	items := barsToJSON(bars)
	if len(items) > limit {
		items = items[len(items)-limit:]
	}
	core["history"] = map[string]interface{}{"items": items, "summary": map[string]interface{}{"count": len(items)}}
	Success(w, core)
}

func (s *Server) SymbolAILatest(w http.ResponseWriter, r *http.Request) {
	symbol := pathParam(r.URL.Path, "/market/symbols/", "/ai/latest")
	market := defaultStr(r.URL.Query().Get("market"), "US")
	data, err := s.DB.LatestAIAnalysis(r.Context(), symbol, market)
	if err != nil {
		response.Error(w, "AI研判查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) FlowBoard(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	kind := defaultStr(q.Get("sectorKind"), "industry")
	limit := intQuery(q.Get("limit"), 20)
	Success(w, s.Flow.GetBoard(r.Context(), kind, limit))
}

func parseIDs(raw string) []int64 {
	parts := strings.Split(raw, ",")
	out := []int64{}
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p == "" {
			continue
		}
		if n, err := strconv.ParseInt(p, 10, 64); err == nil {
			out = append(out, n)
		}
	}
	return out
}

func quoteFromBars(bars []kline.Bar) map[string]interface{} {
	if len(bars) == 0 {
		return map[string]interface{}{}
	}
	last := bars[len(bars)-1]
	lastClose := floatVal(last.Close)
	prevClose := lastClose
	if len(bars) > 1 {
		prevClose = floatVal(bars[len(bars)-2].Close)
	}
	changeRate := 0.0
	if prevClose > 0 {
		changeRate = (lastClose - prevClose) / prevClose * 100
	}
	return map[string]interface{}{
		"last": lastClose, "close": lastClose, "changeRate": changeRate, "tradeDate": last.Date,
	}
}

func floatVal(v *float64) float64 {
	if v == nil {
		return 0
	}
	return *v
}

func barsToJSON(bars []kline.Bar) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(bars))
	for _, bar := range bars {
		out = append(out, map[string]interface{}{
			"date": bar.Date, "open": bar.Open, "high": bar.High, "low": bar.Low,
			"close": bar.Close, "volume": bar.Volume,
		})
	}
	return out
}
