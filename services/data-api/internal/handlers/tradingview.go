package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/market-read/pkg/kline"
)

func (s *Server) TradingViewConfig(w http.ResponseWriter, _ *http.Request) {
	writeRawJSON(w, map[string]interface{}{
		"supported_resolutions":    []string{"D", "W", "M"},
		"supports_group_request":   false,
		"supports_marks":           false,
		"supports_search":          true,
		"supports_time":            true,
		"supports_timescale_marks": false,
	})
}

func (s *Server) TradingViewSymbols(w http.ResponseWriter, r *http.Request) {
	symbol := strings.ToUpper(strings.TrimSpace(r.URL.Query().Get("symbol")))
	if symbol == "" {
		symbol = "AAPL.US"
	}
	name := symbol
	base := symbol
	if i := strings.LastIndex(symbol, "."); i > 0 {
		base = symbol[:i]
	}
	if inst, _ := s.DB.GetInstrumentBySymbol(r.Context(), base); inst != nil && inst["name"] != nil {
		name = fmt.Sprint(inst["name"])
	}
	writeRawJSON(w, map[string]interface{}{
		"name": symbol, "ticker": symbol, "description": name + " (" + symbol + ")",
		"type": "stock", "session": "0930-1600", "timezone": "America/New_York",
		"exchange": "SMART", "minmov": 1, "pricescale": 100, "has_intraday": false,
		"supported_resolutions": []string{"D", "W", "M"}, "volume_precision": 0,
	})
}

func (s *Server) TradingViewHistory(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	symbol := strings.ToUpper(strings.TrimSpace(q.Get("symbol")))
	fromTS, _ := strconv.ParseInt(q.Get("from"), 10, 64)
	toTS, _ := strconv.ParseInt(q.Get("to"), 10, 64)
	resolution := strings.ToUpper(defaultStr(q.Get("resolution"), "D"))
	if resolution != "D" && resolution != "W" && resolution != "M" && resolution != "1D" {
		writeRawJSON(w, map[string]interface{}{"s": "no_data"})
		return
	}
	market, querySymbol := resolveTVSymbol(symbol)
	start := "-5y"
	if fromTS > 0 {
		start = time.Unix(fromTS, 0).UTC().Format("2006-01-02T15:04:05Z")
	}
	stop := "now()"
	if toTS > 0 {
		stop = time.Unix(toTS, 0).UTC().Format("2006-01-02T15:04:05Z")
	}
	limit := 5000
	bars, err := s.Influx.GetKlineSeries(r.Context(), market, querySymbol, "daily", start, stop, &limit)
	if err != nil || len(bars) == 0 {
		writeRawJSON(w, map[string]interface{}{"s": "no_data"})
		return
	}
	t, o, h, l, c, v := barsToTV(bars)
	writeRawJSON(w, map[string]interface{}{"s": "ok", "t": t, "o": o, "h": h, "l": l, "c": c, "v": v})
}

func (s *Server) TradingViewTime(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "text/plain")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(strconv.FormatInt(time.Now().Unix(), 10)))
}

func resolveTVSymbol(symbol string) (market, querySymbol string) {
	market = "US"
	querySymbol = symbol
	if strings.HasSuffix(symbol, ".HK") {
		market = "HK"
	} else if strings.HasSuffix(symbol, ".US") {
		market = "US"
		querySymbol = strings.TrimSuffix(symbol, ".US")
	} else if strings.HasSuffix(symbol, ".SH") || strings.HasSuffix(symbol, ".SZ") {
		market = "CN"
	}
	return market, querySymbol
}

func barsToTV(bars []kline.Bar) (t, o, h, l, c, v []interface{}) {
	for _, bar := range bars {
		ts, err := time.Parse("2006-01-02", bar.Date)
		if err != nil {
			continue
		}
		t = append(t, ts.Unix())
		o = append(o, floatVal(bar.Open))
		h = append(h, floatVal(bar.High))
		l = append(l, floatVal(bar.Low))
		c = append(c, floatVal(bar.Close))
		v = append(v, floatVal(bar.Volume))
	}
	return t, o, h, l, c, v
}

func writeRawJSON(w http.ResponseWriter, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_ = json.NewEncoder(w).Encode(v)
}
