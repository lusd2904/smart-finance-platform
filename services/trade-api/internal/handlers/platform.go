package handlers

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/autoscan"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/platform"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/response"
)

func (s *Server) Notifications(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 50
	}
	data, err := s.Platform.ListNotifications(r.Context(), userID(r), limit)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) NotificationsRead(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	var noticeID *int
	if id := body["id"]; id != nil {
		n, _ := strconv.Atoi(str(id))
		if n > 0 {
			noticeID = &n
		}
	}
	data, err := s.Platform.MarkNotificationRead(r.Context(), userID(r), noticeID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) BacktestRun(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	days, _ := strconv.Atoi(strOr(body["days"], "120"))
	profile := str(body["strategyProfile"])
	if profile == "" {
		profile = str(body["profile"])
	}
	if profile == "" {
		profile = s.Platform.ResolveProfile(r.Context(), userID(r), "")
	}
	data, err := s.Platform.RunBacktest(r.Context(), userID(r), strOr(body["symbol"], "AAPL"), strOr(body["market"], "US"), days, profile)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, str(data["message"]))
}

func (s *Server) BacktestList(w http.ResponseWriter, r *http.Request) {
	data, err := s.Platform.ListBacktests(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) BacktestDetail(w http.ResponseWriter, r *http.Request) {
	idStr := strings.TrimPrefix(r.URL.Path, "/trade/backtest/")
	id, _ := strconv.Atoi(idStr)
	data, err := s.Platform.GetBacktest(r.Context(), userID(r), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) AutoRun(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	uid := userID(r)
	profile := s.Platform.ResolveProfile(r.Context(), uid, str(body["strategyProfile"]))
	if profile == "" {
		profile = s.Platform.ResolveProfile(r.Context(), uid, str(body["strategy_profile"]))
	}
	var execute *bool
	if body["execute"] != nil {
		v := truthy(body["execute"])
		execute = &v
	}
	custom := []platform.Target{}
	if raw := body["symbols"]; raw != nil {
		switch items := raw.(type) {
		case []interface{}:
			for _, it := range items {
				switch row := it.(type) {
				case string:
					code, mkt := parseSymbolMarket(row, "US")
					custom = append(custom, platform.Target{Symbol: code, Market: mkt})
				case map[string]interface{}:
					custom = append(custom, platform.Target{
						Symbol: str(row["symbol"]), Market: strings.ToUpper(strOr(row["market"], "US")),
					})
				}
			}
		}
	}
	cfg := map[string]interface{}{}
	if c, ok := body["customConfig"].(map[string]interface{}); ok {
		cfg = c
	}
	data, err := autoscan.RunWatchlistCycle(r.Context(), s.Platform.Repo, s.Trade.Broker, s.AutoScan, s.Trade.Redis, s.AutoKeys, autoscan.RunInput{
		UserID: uid, Profile: profile, Source: "manual_api", Execute: execute,
		CustomSymbols: custom, CustomConfig: cfg,
	})
	if err != nil {
		response.Error(w, "自动交易扫描失败: "+err.Error())
		return
	}
	response.SuccessMsg(w, data, strOr(data["message"], "扫描完成"))
}

func (s *Server) AiTradeRuns(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 30
	}
	data, err := s.Platform.ListAiTradeRuns(r.Context(), userID(r), limit)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) AutoDecisions(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 50
	}
	data, err := s.Platform.ListAutoDecisions(r.Context(), limit, r.URL.Query().Get("cycle_id"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) Coverage(w http.ResponseWriter, r *http.Request) {
	data, err := s.Platform.HistoryCoverage(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) StrategyProfiles(w http.ResponseWriter, r *http.Request) {
	data, err := s.Platform.ListStrategyProfiles(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) SaveStrategyProfile(w http.ResponseWriter, r *http.Request) {
	code := strings.TrimPrefix(r.URL.Path, "/trade/strategy-profiles/")
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	name := strOr(body["profileName"], code)
	cfg := body
	if c, ok := body["config"].(map[string]interface{}); ok {
		cfg = c
	}
	if err := s.Platform.SaveStrategyProfile(r.Context(), userID(r), code, name, cfg); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, nil, "已保存本账户策略档位")
}

func (s *Server) BindStrategy(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	code, err := s.Platform.BindStrategy(r.Context(), userID(r), strOr(body["profileCode"], str(body["profile"])))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, map[string]interface{}{"profileCode": code}, "已绑定本账户生效策略")
}

func (s *Server) RiskTearsheet(w http.ResponseWriter, r *http.Request) {
	days, _ := strconv.Atoi(r.URL.Query().Get("days"))
	if days <= 0 {
		days = 120
	}
	data, err := s.Platform.RiskTearsheet(r.Context(), userID(r), days)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, strOr(data["message"], "操作成功"))
}

func (s *Server) RiskRules(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		data, err := s.Platform.ListRiskRules(r.Context())
		if err != nil {
			response.Error(w, err.Error())
			return
		}
		response.Success(w, data)
	case http.MethodPost:
		body, err := readJSON(r)
		if err != nil {
			response.Error(w, "请求体无效")
			return
		}
		id, err := s.Platform.SaveRiskRule(r.Context(), body)
		if err != nil {
			response.Error(w, err.Error())
			return
		}
		response.SuccessMsg(w, map[string]interface{}{"ruleId": id}, "保存成功")
	default:
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
	}
}

func (s *Server) DeleteRiskRule(w http.ResponseWriter, r *http.Request) {
	idStr := strings.TrimPrefix(r.URL.Path, "/trade/risk/rules/")
	id, _ := strconv.Atoi(idStr)
	if err := s.Platform.DeleteRiskRule(r.Context(), id); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, nil, "删除成功")
}

func (s *Server) RiskEvents(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 50
	}
	data, err := s.Platform.ListRiskEvents(r.Context(), userID(r), limit, r.URL.Query().Get("status"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) RiskEvaluate(w http.ResponseWriter, r *http.Request) {
	data, err := s.Platform.EvaluateRisk(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, "生成 "+str(data["created"])+" 条事件")
}

func (s *Server) UpdateRiskEventStatus(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/trade/risk/events/")
	idStr := strings.TrimSuffix(path, "/status")
	id, _ := strconv.Atoi(idStr)
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	operator := ""
	data, err := s.Platform.UpdateRiskEventStatus(r.Context(), userID(r), id, body, operator)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, "更新风控状态成功")
}

func (s *Server) Notices(w http.ResponseWriter, r *http.Request) {
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	if limit <= 0 {
		limit = 50
	}
	data, err := s.Platform.ListNotices(r.Context(), userID(r), limit)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) NoticesRead(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	var noticeID *int
	if id := body["id"]; id != nil {
		n, _ := strconv.Atoi(str(id))
		if n > 0 {
			noticeID = &n
		}
	}
	if err := s.Platform.MarkNoticeRead(r.Context(), userID(r), noticeID); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, nil, "ok")
}

func (s *Server) SubmitAiBatch(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	market := strOr(body["market"], "US")
	days, _ := strconv.Atoi(strOr(body["days"], "90"))
	symbols := []string{}
	if raw, ok := body["symbols"].([]interface{}); ok {
		for _, it := range raw {
			if sym := strings.TrimSpace(str(it)); sym != "" {
				symbols = append(symbols, sym)
			}
		}
	}
	data, err := s.Platform.SubmitAiBatch(r.Context(), symbols, market, days)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, "已加入后台队列")
}

func (s *Server) AiBatches(w http.ResponseWriter, r *http.Request) {
	data, err := s.Platform.ListAiBatches(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) AiBatchItems(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/trade/ai/batches/")
	idStr := strings.TrimSuffix(path, "/items")
	id, _ := strconv.Atoi(idStr)
	data, err := s.Platform.ListAiBatchItems(r.Context(), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) GetFeishuConfig(w http.ResponseWriter, r *http.Request) {
	data, err := s.Platform.GetFeishuConfig(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) PutFeishuConfig(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	data, err := s.Platform.SaveFeishuConfig(r.Context(), userID(r), body)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, "订阅已保存")
}

func (s *Server) TestFeishu(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	channel := strOr(body["channel"], "personal")
	data, err := s.Platform.TestFeishu(r.Context(), userID(r), channel)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, data, strOr(data["message"], "已发送"))
}

func parseSymbolMarket(symbol, market string) (string, string) {
	parts := strings.Split(symbol, ".")
	if len(parts) == 2 {
		return parts[0], strings.ToUpper(parts[1])
	}
	return symbol, strings.ToUpper(market)
}
