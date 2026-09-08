package handlers

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/ingest"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/proxy"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/queue"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/store"
)

type Server struct {
	Cfg    *config.Config
	Store  *store.Store
	Queue  *queue.Enqueuer
	AIProxy *proxy.PythonIntel
}

func (s *Server) Health(w http.ResponseWriter, _ *http.Request) {
	response.Success(w, map[string]string{"status": "ok", "service": "sfp-intel"})
}

func (s *Server) IngestXMonitor(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.NotFound(w, r)
		return
	}
	token := r.Header.Get("X-Ingest-Token")
	if err := ingest.VerifyToken(token, s.Cfg.XMonitorIngestToken); err != nil {
		msg := err.Error()
		switch msg {
		case "missing ingest token":
			response.Unauthorized(w, msg)
		default:
			response.Forbidden(w, msg)
		}
		return
	}
	var body struct {
		Items []map[string]interface{} `json:"items"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	data, err := s.Store.IngestXMonitor(r.Context(), body.Items)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) NewsList(w http.ResponseWriter, r *http.Request) {
	q := store.NewsQuery{
		Source: r.URL.Query().Get("source"),
		Title:  r.URL.Query().Get("title"),
		Analyzed: r.URL.Query().Get("analyzed"),
		BeginTime: r.URL.Query().Get("beginTime"),
		EndTime: r.URL.Query().Get("endTime"),
		PageNum: queryInt(r, "pageNum", 1),
		PageSize: queryInt(r, "pageSize", 10),
	}
	rows, total, err := s.Store.ListNews(r.Context(), q)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Page(w, store.FormatNewsRows(rows), q.PageNum, q.PageSize, total)
}

func (s *Server) DeleteNews(w http.ResponseWriter, r *http.Request) {
	idsRaw := strings.TrimPrefix(r.URL.Path, "/sentiment/news/")
	idsRaw = strings.Trim(idsRaw, "/")
	parts := strings.Split(idsRaw, ",")
	ids := make([]int64, 0, len(parts))
	for _, p := range parts {
		if p == "" {
			continue
		}
		id, err := strconv.ParseInt(p, 10, 64)
		if err != nil {
			response.Error(w, "invalid news id")
			return
		}
		ids = append(ids, id)
	}
	if err := s.Store.DeleteNews(r.Context(), ids); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "删除成功", nil)
}

func (s *Server) CollectNews(w http.ResponseWriter, r *http.Request) {
	ticket, err := s.Queue.Submit(r.Context(), "sentiment_collect", map[string]any{"analyze": false})
	if err != nil {
		response.Error(w, "后台任务队列暂不可用，请稍后重试")
		return
	}
	response.SuccessMsg(w, "已加入后台队列，稍后刷新资讯列表", ticket)
}

func (s *Server) Stats(w http.ResponseWriter, r *http.Request) {
	stats, err := s.Store.CountNews(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	latest, err := s.Store.LatestAnalysis(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	out := map[string]interface{}{
		"total": stats["total"],
		"today": stats["today"],
		"unanalyzed": stats["unanalyzed"],
	}
	if latest != nil {
		out["latestAnalysis"] = store.FormatAnalysisRow(latest)
	} else {
		out["latestAnalysis"] = nil
	}
	response.Success(w, out)
}

func (s *Server) AnalysisList(w http.ResponseWriter, r *http.Request) {
	q := store.AnalysisQuery{
		Status: r.URL.Query().Get("status"),
		BeginTime: r.URL.Query().Get("beginTime"),
		EndTime: r.URL.Query().Get("endTime"),
		PageNum: queryInt(r, "pageNum", 1),
		PageSize: queryInt(r, "pageSize", 10),
	}
	rows, total, err := s.Store.ListAnalysis(r.Context(), q)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Page(w, store.FormatAnalysisRows(rows), q.PageNum, q.PageSize, total)
}

func (s *Server) AnalysisTrend(w http.ResponseWriter, r *http.Request) {
	limit := queryInt(r, "limit", 24)
	trend, err := s.Store.RecentAnalysisTrend(r.Context(), limit)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, trend)
}

func (s *Server) RunAnalysis(w http.ResponseWriter, r *http.Request) {
	ticket, err := s.Queue.Submit(r.Context(), "sentiment_analyze", map[string]any{})
	if err != nil {
		response.Error(w, "后台任务队列暂不可用，请稍后重试")
		return
	}
	response.SuccessMsg(w, "已加入后台队列，稍后刷新分析结果", ticket)
}

func (s *Server) AnalysisDetail(w http.ResponseWriter, r *http.Request) {
	idRaw := strings.TrimPrefix(r.URL.Path, "/sentiment/analysis/")
	id, err := strconv.ParseInt(strings.Trim(idRaw, "/"), 10, 64)
	if err != nil {
		response.Error(w, "invalid analysis id")
		return
	}
	row, err := s.Store.GetAnalysis(r.Context(), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	if row == nil {
		response.Error(w, "分析结果不存在")
		return
	}
	response.Success(w, store.FormatAnalysisRow(row))
}

func (s *Server) GetConfig(w http.ResponseWriter, r *http.Request) {
	cfg, err := s.Store.GetAiConfig(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, cfg)
}

func (s *Server) SaveConfig(w http.ResponseWriter, r *http.Request) {
	var body struct {
		MaxNewsPerRound int    `json:"maxNewsPerRound"`
		AutoAnalyze     string `json:"autoAnalyze"`
		EnabledSources  string `json:"enabledSources"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		response.Error(w, "invalid json")
		return
	}
	user := auth.UserFrom(r.Context())
	userName := "system"
	if user != nil && user.UserName != "" {
		userName = user.UserName
	}
	if body.MaxNewsPerRound <= 0 {
		body.MaxNewsPerRound = 200
	}
	if body.AutoAnalyze == "" {
		body.AutoAnalyze = "1"
	}
	if body.EnabledSources == "" {
		body.EnabledSources = "eastmoney,sina,ths,wallstreetcn,google_news"
	}
	if err := s.Store.SaveAiConfig(r.Context(), body.MaxNewsPerRound, body.AutoAnalyze, body.EnabledSources, userName); err != nil {
		response.Error(w, err.Error())
		return
	}
	response.SuccessMsg(w, "保存成功", nil)
}

func (s *Server) ProxyAI(w http.ResponseWriter, r *http.Request) {
	if s.AIProxy == nil {
		response.Error(w, "AI proxy not configured")
		return
	}
	s.AIProxy.ServeHTTP(w, r)
}

func queryInt(r *http.Request, key string, fallback int) int {
	v := strings.TrimSpace(r.URL.Query().Get(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}
