package handlers

import (
	"database/sql"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/heat"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/influx"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/kline"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/quotes"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/store"
)

type Server struct {
	Auth   *auth.Authenticator
	Influx *influx.Client
	Heat   *store.HeatStore
	Cache  *cache.Cache
	Quotes *quotes.Service
}

func (s *Server) Health(w http.ResponseWriter, _ *http.Request) {
	response.Success(w, map[string]string{"status": "ok", "service": "market-read"})
}

func (s *Server) Kline(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	symbol := q.Get("symbol")
	market := q.Get("market")
	if market == "" {
		market = "US"
	}
	period := q.Get("period")
	start := q.Get("start")
	stop := q.Get("stop")
	if stop == "" {
		stop = "now()"
	}
	var limit *int
	if raw := q.Get("limit"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			limit = &n
		}
	}
	bars, err := s.Influx.GetKlineSeries(r.Context(), market, symbol, period, start, stop, limit)
	if err != nil {
		response.Error(w, "InfluxDB 查询K线失败")
		return
	}
	response.Success(w, map[string]interface{}{
		"symbol": symbol,
		"market": market,
		"klines": toJSONBars(bars),
	})
}

func (s *Server) SymbolHistory(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/market/symbols/")
	path = strings.TrimSuffix(path, "/history")
	symbol := path
	if i := strings.Index(symbol, "/"); i >= 0 {
		symbol = symbol[:i]
	}
	q := r.URL.Query()
	market := q.Get("market")
	if market == "" {
		market = "US"
	}
	limit := 120
	if raw := q.Get("limit"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			limit = n
		}
	}
	if limit < 1 {
		limit = 1
	}
	if limit > 500 {
		limit = 500
	}
	bars, err := s.Influx.GetKlineSeries(r.Context(), market, symbol, "daily", "-2y", "now()", &limit)
	if err != nil {
		response.Error(w, "InfluxDB 查询K线失败")
		return
	}
	if len(bars) > limit {
		bars = bars[len(bars)-limit:]
	}
	response.Success(w, map[string]interface{}{
		"symbol": symbol,
		"market": market,
		"items":  toJSONBars(bars),
		"count":  len(bars),
	})
}

func (s *Server) BoardQuotes(w http.ResponseWriter, r *http.Request) {
	category := r.URL.Query().Get("category")
	market := r.URL.Query().Get("market")
	ctx := r.Context()

	cached, err := s.Cache.GetJSON(ctx, cache.BoardQuotesKey)
	if err == nil && hasQuotes(cached) {
		payload := cache.FilterBoardPayload(cached, category, market)
		if payload["source"] == nil {
			payload["source"] = "cache"
		}
		payload["stale"] = false
		response.Success(w, payload)
		return
	}
	scheduled, err := s.Cache.GetJSON(ctx, cache.ScheduledBoard)
	if err == nil && scheduled != nil && scheduled["items"] != nil {
		adapted := cache.AdaptScheduledBoard(scheduled)
		payload := cache.FilterBoardPayload(adapted, category, market)
		payload["source"] = "scheduled"
		payload["stale"] = true
		response.Success(w, payload)
		return
	}
	response.Success(w, map[string]interface{}{
		"quotes":  []interface{}{},
		"indices": []interface{}{},
		"rows":    []interface{}{},
		"source":  "empty",
		"stale":   true,
		"count":   0,
		"message": "看板缓存尚未生成，请等待 jobs 预热",
	})
}

func (s *Server) HeatDaily(w http.ResponseWriter, r *http.Request) {
	market, err := heat.NormalizeMarket(r.URL.Query().Get("market"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	tradeDate := strings.TrimSpace(r.URL.Query().Get("tradeDate"))
	ctx := r.Context()
	var heatRow *store.HeatRow
	sessionDate := tradeDate
	if sessionDate != "" {
		if len(sessionDate) >= 10 {
			sessionDate = sessionDate[:10]
		}
		heatRow, err = s.Heat.GetHeat(ctx, market, sessionDate)
	} else {
		heatRow, err = s.Heat.GetLatestHeat(ctx, market)
		if heatRow != nil {
			sessionDate = heatRow.TradeDate
		}
	}
	if err != nil {
		response.Error(w, "热度查询失败")
		return
	}
	if heatRow == nil {
		if sessionDate == "" {
			sessionDate = todayInMarket(market)
		}
		response.Success(w, map[string]interface{}{
			"market":      market,
			"tradeDate":   sessionDate,
			"empty":       true,
			"loadingHint": "暂无该日热度快照，收盘任务完成后将自动写入。",
			"heat":        nil,
			"top50":       []interface{}{},
			"meta":        store.MarketMeta(market),
		})
		return
	}
	top50Rows, err := s.Heat.ListTop50(ctx, market, heatRow.TradeDate)
	if err != nil {
		response.Error(w, "Top50 查询失败")
		return
	}
	top50 := store.SerializeTop50(top50Rows)
	s.Heat.FillMissingLastFromDaily(ctx, market, heatRow.TradeDate, top50)
	board, _ := s.Cache.GetJSON(ctx, cache.BoardQuotesKey)
	cache.EnrichTop50Last(top50, board, market)

	user := auth.UserFrom(ctx)
	if user != nil {
		watch, _ := s.Heat.WatchlistSymbols(ctx, user.UserID)
		for _, item := range top50 {
			key := strings.ToUpper(fmt.Sprint(item["symbol"])) + "|" + market
			item["inWatchlist"] = watch[key]
		}
	}
	response.Success(w, map[string]interface{}{
		"market":    market,
		"tradeDate": heatRow.TradeDate,
		"empty":     false,
		"heat":      store.SerializeHeat(heatRow),
		"top50":     top50,
		"meta":      store.MarketMeta(market),
	})
}

func (s *Server) HeatTrend(w http.ResponseWriter, r *http.Request) {
	market, err := heat.NormalizeMarket(r.URL.Query().Get("market"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	days := 5
	if raw := r.URL.Query().Get("days"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			days = n
		}
	}
	rows, err := s.Heat.ListHeatTrend(r.Context(), market, days)
	if err != nil {
		response.Error(w, "热度趋势查询失败")
		return
	}
	points := make([]map[string]interface{}, 0, len(rows))
	for _, row := range rows {
		points = append(points, map[string]interface{}{
			"tradeDate":      row.TradeDate,
			"indexChangePct": sqlNullFloat(row.IndexChangePct),
			"totalTurnover":  sqlNullFloat(row.TotalTurnover),
			"heatScore":      sqlNullFloat(row.HeatScore),
			"advanceCount":   sqlNullInt(row.AdvanceCount),
			"declineCount":   sqlNullInt(row.DeclineCount),
		})
	}
	response.Success(w, map[string]interface{}{"market": market, "days": days, "points": points})
}

func (s *Server) HeatDates(w http.ResponseWriter, r *http.Request) {
	market, err := heat.NormalizeMarket(r.URL.Query().Get("market"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	limit := 30
	if raw := r.URL.Query().Get("limit"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil {
			limit = n
		}
	}
	rows, err := s.Heat.ListHeatTrend(r.Context(), market, limit)
	if err != nil {
		response.Error(w, "交易日查询失败")
		return
	}
	dates := make([]string, 0, len(rows))
	for _, row := range rows {
		dates = append(dates, row.TradeDate)
	}
	response.Success(w, map[string]interface{}{"market": strings.ToUpper(market), "dates": dates})
}

func (s *Server) HeatConfig(w http.ResponseWriter, r *http.Request) {
	weights := s.Cache.ResolveHeatWeights(r.Context())
	markets := map[string]interface{}{}
	for code, meta := range heat.MarketMeta {
		markets[code] = map[string]interface{}{
			"label":         meta.Label,
			"currency":      meta.Currency,
			"indexSymbol":   meta.IndexSymbol,
			"indexName":     meta.IndexName,
			"capFilterRule": meta.CapRule,
		}
	}
	keys := make([]string, 0, len(heat.WeightConfigKeys))
	for k := range heat.WeightConfigKeys {
		keys = append(keys, k)
	}
	response.Success(w, map[string]interface{}{
		"weights":    weights,
		"markets":    markets,
		"configKeys": keys,
	})
}

func (s *Server) IndexQuotes(w http.ResponseWriter, r *http.Request) {
	if s.Quotes != nil {
		response.Success(w, s.Quotes.IndexQuotes(r.Context()))
		return
	}
	cached, err := s.Cache.GetJSON(r.Context(), cache.IndexQuotesKey)
	if err == nil && cached != nil {
		cached["cached"] = true
		response.Success(w, cached)
		return
	}
	response.Success(w, map[string]interface{}{
		"items":  []interface{}{},
		"asOf":   nil,
		"cached": false,
	})
}

func (s *Server) LiveQuotes(w http.ResponseWriter, r *http.Request) {
	pairs := quotes.ParseSymbolsQuery(r.URL.Query().Get("symbols"))
	if s.Quotes == nil {
		response.Success(w, map[string]interface{}{
			"items":  []interface{}{},
			"asOf":   nil,
			"source": "empty",
			"cached": false,
		})
		return
	}
	response.Success(w, s.Quotes.LiveQuotes(r.Context(), pairs))
}

func toJSONBars(bars []kline.Bar) []map[string]interface{} {
	out := make([]map[string]interface{}, 0, len(bars))
	for _, bar := range bars {
		out = append(out, map[string]interface{}{
			"date":   bar.Date,
			"open":   bar.Open,
			"high":   bar.High,
			"low":    bar.Low,
			"close":  bar.Close,
			"volume": bar.Volume,
		})
	}
	return out
}

func hasQuotes(payload map[string]interface{}) bool {
	if payload == nil {
		return false
	}
	if q, ok := payload["quotes"].([]interface{}); ok && len(q) > 0 {
		return true
	}
	if rows, ok := payload["rows"].([]interface{}); ok && len(rows) > 0 {
		return true
	}
	return false
}

func sqlNullFloat(v sql.NullFloat64) interface{} {
	if v.Valid {
		return v.Float64
	}
	return nil
}

func sqlNullInt(v sql.NullInt64) interface{} {
	if v.Valid {
		return v.Int64
	}
	return nil
}

func todayInMarket(market string) string {
	meta, ok := heat.MarketMeta[strings.ToUpper(market)]
	if !ok {
		return time.Now().UTC().Format("2006-01-02")
	}
	loc, err := time.LoadLocation(meta.Timezone)
	if err != nil {
		return time.Now().UTC().Format("2006-01-02")
	}
	return time.Now().In(loc).Format("2006-01-02")
}
