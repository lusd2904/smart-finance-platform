package handlers

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/response"
)

func (s *Server) GetJobTicket(w http.ResponseWriter, r *http.Request) {
	jobID := strings.TrimPrefix(r.URL.Path, "/market/jobs/")
	jobID = strings.Trim(jobID, "/")
	if jobID == "" {
		response.Error(w, "任务不存在或已过期")
		return
	}
	ticket, err := s.Queue.GetTicket(r.Context(), jobID)
	if err != nil || ticket == nil {
		response.Error(w, "任务不存在或已过期")
		return
	}
	Success(w, ticket)
}

func (s *Server) submitJob(w http.ResponseWriter, r *http.Request, jobType string, payload map[string]interface{}, okMsg string) {
	ticket, err := s.Queue.Submit(r.Context(), jobType, payload)
	if err != nil || ticket == nil {
		response.Error(w, "后台任务队列暂不可用，请稍后重试")
		return
	}
	SuccessMsg(w, okMsg, ticket)
}

func (s *Server) MarketSync(w http.ResponseWriter, r *http.Request) {
	body := map[string]interface{}{"years": 10}
	if r.Body != nil {
		defer r.Body.Close()
		var req map[string]interface{}
		if json.NewDecoder(r.Body).Decode(&req) == nil {
			if y, ok := req["years"]; ok {
				body["years"] = y
			}
			if sym, ok := req["symbol"]; ok {
				body["symbol"] = sym
			}
		}
	}
	s.submitJob(w, r, "market_sync", body, "已加入后台队列，稍后刷新查看结果")
}

func (s *Server) MySQLToInflux(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	payload := map[string]interface{}{
		"symbol": q.Get("symbol"),
		"market": defaultStr(q.Get("market"), "US"),
	}
	s.submitJob(w, r, "mysql_to_influx", payload, "已加入后台队列，稍后刷新查看结果")
}

func (s *Server) HeatCollect(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	payload := map[string]interface{}{
		"market":    strings.ToUpper(defaultStr(q.Get("market"), "US")),
		"tradeDate": q.Get("tradeDate"),
	}
	s.submitJob(w, r, "market_heat_collect", payload, "已加入后台队列")
}

func (s *Server) StockPickRun(w http.ResponseWriter, r *http.Request) {
	s.submitJob(w, r, "stock_pick_run", map[string]interface{}{"trigger": "manual", "useAi": true}, "已加入选股队列，稍后刷新")
}

func (s *Server) StockPickMoodRefresh(w http.ResponseWriter, r *http.Request) {
	ticket, err := s.Queue.Submit(r.Context(), "sentiment_collect", map[string]interface{}{"analyze": true})
	if err != nil || ticket == nil {
		response.Error(w, "队列不可用，请稍后在任务中心执行舆情采集")
		return
	}
	SuccessMsg(w, "已排队刷新舆情", ticket)
}

func (s *Server) MarketAIAnalyze(w http.ResponseWriter, r *http.Request) {
	body, err := readJSONBody(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	payload := map[string]interface{}{
		"symbol": body["symbol"],
		"market": defaultStr(fmt.Sprint(body["market"]), "US"),
		"days":   intOr(body["days"], 120),
	}
	s.submitJob(w, r, "ai_analyze", payload, "已加入后台队列")
}

func (s *Server) SymbolAIAnalyze(w http.ResponseWriter, r *http.Request) {
	symbol := pathParam(r.URL.Path, "/market/symbols/", "/ai-analyze")
	q := r.URL.Query()
	payload := map[string]interface{}{
		"symbol": symbol,
		"market": defaultStr(q.Get("market"), "US"),
		"days":   intQuery(q.Get("days"), 120),
	}
	s.submitJob(w, r, "ai_analyze", payload, "已加入后台队列")
}

func (s *Server) WatchlistAnalyze(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	body, _ := readJSONBody(r)
	payload := map[string]interface{}{"userId": userID}
	if body != nil {
		if sym, ok := body["symbol"]; ok && sym != nil && fmt.Sprint(sym) != "" {
			payload["symbol"] = sym
			payload["market"] = body["market"]
		}
		if rc, ok := body["refreshContent"]; ok {
			payload["refreshContent"] = rc
		}
	}
	s.submitJob(w, r, "watchlist_analyze", payload, "已加入后台队列，稍后刷新清单查看结果")
}

func (s *Server) ReviewAnalyze(w http.ResponseWriter, r *http.Request) {
	market := r.URL.Query().Get("market")
	var markets interface{}
	if market != "" {
		markets = []string{market}
	}
	s.submitJob(w, r, "market_review", map[string]interface{}{"markets": markets}, "已加入后台队列")
}

func (s *Server) QuantScanDaily(w http.ResponseWriter, r *http.Request) {
	profile := defaultStr(r.URL.Query().Get("profile"), "balanced")
	s.submitJob(w, r, "factor_scan", map[string]interface{}{"profile": profile}, "已加入后台队列，稍后刷新查看结果")
}

func (s *Server) QuantFactorQCRun(w http.ResponseWriter, r *http.Request) {
	market := strings.ToUpper(defaultStr(r.URL.Query().Get("market"), "US"))
	s.submitJob(w, r, "factor_qc", map[string]interface{}{"market": market}, "已加入后台队列，稍后刷新查看结果")
}

func (s *Server) QuantStrategyRun(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	body, _ := readJSONBody(r)
	payload := map[string]interface{}{"userId": userID}
	if body != nil {
		if syms, ok := body["symbols"]; ok {
			payload["symbols"] = syms
		}
		if p, ok := body["profile"]; ok && fmt.Sprint(p) != "" {
			payload["profile"] = p
		}
	}
	s.submitJob(w, r, "strategy_run", payload, "已加入后台队列，稍后在策略历史中查看结果")
}

func (s *Server) QuantDailyListScan(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	body, _ := readJSONBody(r)
	payload := map[string]interface{}{"userId": userID}
	if body != nil {
		if p, ok := body["profile"]; ok && fmt.Sprint(p) != "" {
			payload["profile"] = fmt.Sprint(p)
		}
	}
	s.submitJob(w, r, "daily_list_scan", payload, "已加入后台队列")
}

func readJSONBody(r *http.Request) (map[string]interface{}, error) {
	if r.Body == nil {
		return map[string]interface{}{}, nil
	}
	defer r.Body.Close()
	raw, err := io.ReadAll(r.Body)
	if err != nil || len(raw) == 0 {
		return map[string]interface{}{}, err
	}
	var out map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func defaultStr(v, fallback string) string {
	if strings.TrimSpace(v) == "" {
		return fallback
	}
	return v
}

func intQuery(raw string, fallback int) int {
	if raw == "" {
		return fallback
	}
	n, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return n
}

func intOr(v interface{}, fallback int) int {
	switch n := v.(type) {
	case float64:
		return int(n)
	case int:
		return n
	case json.Number:
		i, _ := n.Int64()
		return int(i)
	default:
		return fallback
	}
}

func pathParam(path, prefix, suffix string) string {
	p := strings.TrimPrefix(path, prefix)
	p = strings.TrimSuffix(p, suffix)
	if i := strings.Index(p, "/"); i >= 0 {
		p = p[:i]
	}
	return p
}
