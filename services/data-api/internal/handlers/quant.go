package handlers

import (
	"encoding/csv"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/response"
	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/timeutil"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/factor"
)

func (s *Server) FactorSchema(w http.ResponseWriter, r *http.Request) {
	Success(w, factor.GetSchema())
}

func (s *Server) FactorSnapshots(w http.ResponseWriter, r *http.Request) {
	items, err := s.DB.ListFactorSnapshots(r.Context(), intQuery(r.URL.Query().Get("limit"), 80))
	if err != nil {
		response.Error(w, "因子快照查询失败")
		return
	}
	Success(w, items)
}

func (s *Server) FactorSnapshotsExport(w http.ResponseWriter, r *http.Request) {
	items, err := s.DB.ListFactorSnapshots(r.Context(), 200)
	if err != nil {
		response.Error(w, "因子快照导出失败")
		return
	}
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="factor_snapshots_%s.csv"`, time.Now().Format("20060102_150405")))
	w.Write([]byte("\ufeff"))
	writer := csv.NewWriter(w)
	_ = writer.Write([]string{"symbol", "market", "asOf", "total", "riskLevel", "trendDirection", "alpha101Count", "alpha158Count", "alphaCsCount", "createTime"})
	for _, it := range items {
		_ = writer.Write([]string{
			fmt.Sprint(it["symbol"]), fmt.Sprint(it["market"]), fmt.Sprint(it["asOf"]),
			fmt.Sprint(it["total"]), fmt.Sprint(it["riskLevel"]), fmt.Sprint(it["trendDirection"]),
			fmt.Sprint(it["alpha101Count"]), fmt.Sprint(it["alpha158Count"]), fmt.Sprint(it["alphaCsCount"]),
			fmt.Sprint(it["createTime"]),
		})
	}
	writer.Flush()
}

func (s *Server) FactorQC(w http.ResponseWriter, r *http.Request) {
	market := defaultStr(r.URL.Query().Get("market"), "US")
	data, err := s.DB.FactorQCReport(r.Context(), market)
	if err != nil {
		response.Error(w, "因子质检查询失败")
		return
	}
	SuccessMsg(w, fmt.Sprint(data["message"]), data)
}

func (s *Server) QuantWatchlistList(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	q := r.URL.Query()
	page, err := s.DB.QuantWatchlistPage(r.Context(), userID, q.Get("symbol"), q.Get("market"), q.Get("enabled"),
		intQuery(q.Get("pageNum"), 1), intQuery(q.Get("pageSize"), 10))
	if err != nil {
		response.Error(w, "量化自选查询失败")
		return
	}
	SuccessPage(w, page)
}

func (s *Server) QuantWatchlistAdd(w http.ResponseWriter, r *http.Request) {
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
	if err := s.DB.AddQuantWatchlist(r.Context(), userID, fmt.Sprint(body["symbol"]), fmt.Sprint(body["market"]), fmt.Sprint(body["note"])); err != nil {
		response.Error(w, "新增量化自选失败")
		return
	}
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: "新增成功", Success: true, Time: timeutil.NowBeijingRFC()})
}

func (s *Server) QuantWatchlistDelete(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	idsRaw := strings.TrimPrefix(r.URL.Path, "/quant/watchlist/")
	if err := s.DB.DeleteQuantWatchlist(r.Context(), userID, parseIDs(idsRaw)); err != nil {
		response.Error(w, "删除量化自选失败")
		return
	}
	writeEnvelope(w, http.StatusOK, envelope{Code: 200, Msg: "删除成功", Success: true, Time: timeutil.NowBeijingRFC()})
}

func (s *Server) StrategyHistory(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	q := r.URL.Query()
	page, err := s.DB.StrategyHistoryPage(r.Context(), userID, q.Get("strategyProfile"), q.Get("beginTime"), q.Get("endTime"),
		intQuery(q.Get("pageNum"), 1), intQuery(q.Get("pageSize"), 10))
	if err != nil {
		response.Error(w, "策略历史查询失败")
		return
	}
	SuccessPage(w, page)
}

func (s *Server) ScanRuns(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	data, err := s.DB.ScanRuns(r.Context(), userID, intQuery(r.URL.Query().Get("limit"), 20))
	if err != nil {
		response.Error(w, "扫描台账查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) ScanRunDetail(w http.ResponseWriter, r *http.Request) {
	cycleID := strings.TrimPrefix(r.URL.Path, "/quant/scan-runs/")
	cycleID = strings.Trim(cycleID, "/")
	data, err := s.DB.ScanRunDetail(r.Context(), cycleID)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	Success(w, data)
}

func (s *Server) SymbolLatestScan(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	symbol := pathParam(r.URL.Path, "/quant/symbols/", "/latest")
	market := defaultStr(r.URL.Query().Get("market"), "US")
	data, err := s.DB.SymbolLatestScan(r.Context(), userID, symbol, market)
	if err != nil {
		response.Error(w, "标的扫描查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) DailyList(w http.ResponseWriter, r *http.Request) {
	userID, err := requireUser(r.Context())
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	data, err := s.DB.DailyListLatest(r.Context(), userID)
	if err != nil {
		response.Error(w, "次日清单查询失败")
		return
	}
	Success(w, data)
}

func (s *Server) ReadmodelOverview(w http.ResponseWriter, r *http.Request) {
	snapshot, err := s.Cache.GetJSON(r.Context(), "readmodel:scheduled:overview")
	if err != nil || snapshot == nil {
		Success(w, map[string]interface{}{
			"configured": false,
			"message":    "量化读模型暂不可用，长桥服务或密钥未配置",
			"asset": map[string]interface{}{
				"configured": false, "totalCash": nil, "netAssets": nil,
				"availableCash": nil, "currency": nil,
			},
			"position": map[string]interface{}{"count": 0, "positions": []interface{}{}},
		})
		return
	}
	Success(w, snapshot)
}
