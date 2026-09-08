package handlers

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/auth"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/response"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/service"
)

type Server struct {
	Trade *service.Trade
}

func (s *Server) Health(w http.ResponseWriter, _ *http.Request) {
	response.Success(w, map[string]string{"status": "ok", "service": "trade-api"})
}

func userID(r *http.Request) int {
	u := auth.UserFrom(r.Context())
	if u == nil {
		return 0
	}
	return int(u.UserID)
}

func (s *Server) Account(w http.ResponseWriter, r *http.Request) {
	data, err := s.Trade.Account(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) Positions(w http.ResponseWriter, r *http.Request) {
	data, err := s.Trade.Positions(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) Orders(w http.ResponseWriter, r *http.Request) {
	data, err := s.Trade.Orders(r.Context(), userID(r), r.URL.Query().Get("scope"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) OrderDetail(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/trade/order/")
	data, err := s.Trade.OrderDetail(r.Context(), userID(r), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) SubmitOrder(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	qty, _ := strconv.ParseFloat(str(body["quantity"]), 64)
	priceRaw := body["price"]
	hasPrice := priceRaw != nil && str(priceRaw) != ""
	price := 0.0
	if hasPrice {
		price, _ = strconv.ParseFloat(str(priceRaw), 64)
	}
	data, err := s.Trade.SubmitOrder(r.Context(), userID(r), service.SubmitInput{
		Symbol:    str(body["symbol"]),
		Side:      str(body["side"]),
		Quantity:  qty,
		OrderType: strOr(body["orderType"], "LO"),
		Price:     price,
		HasPrice:  hasPrice,
		Market:    strOr(body["market"], "US"),
	})
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) CancelOrder(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/trade/order/")
	id := strings.TrimSuffix(path, "/cancel")
	data, err := s.Trade.CancelOrder(r.Context(), userID(r), id)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) QuoteRealtime(w http.ResponseWriter, r *http.Request) {
	raw := r.URL.Query().Get("symbols")
	parts := make([]string, 0)
	for _, p := range strings.Split(raw, ",") {
		if t := strings.TrimSpace(p); t != "" {
			parts = append(parts, t)
		}
	}
	data, err := s.Trade.RealtimeQuotes(r.Context(), userID(r), parts, r.URL.Query().Get("market"))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) GetHalt(w http.ResponseWriter, r *http.Request) {
	h := s.Trade.ReadHalt(r.Context())
	response.Success(w, map[string]interface{}{
		"halted": h.Halted,
		"reason": h.Reason,
		"by":     h.By,
		"at":     h.At,
	})
}

func (s *Server) PutHalt(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	halted := false
	if v, ok := body["halted"]; ok {
		halted = truthy(v)
	} else if v, ok := body["halt"]; ok {
		halted = truthy(v)
	}
	h := s.Trade.WriteHalt(r.Context(), halted, str(body["reason"]), userID(r))
	response.Success(w, map[string]interface{}{
		"halted": h.Halted,
		"reason": h.Reason,
		"by":     h.By,
		"at":     h.At,
	})
}

func (s *Server) AutoStatus(w http.ResponseWriter, r *http.Request) {
	data, err := s.Trade.AutoStatus(r.Context(), userID(r))
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func (s *Server) AutoSettings(w http.ResponseWriter, r *http.Request) {
	body, err := readJSON(r)
	if err != nil {
		response.Error(w, "请求体无效")
		return
	}
	enabled := truthy(body["autoTradeEnabled"])
	ratio, _ := strconv.ParseFloat(strOr(body["dailyBuyRatio"], str(body["buyRatio"])), 64)
	if ratio == 0 {
		ratio = 0.20
	}
	pct, _ := strconv.ParseFloat(str(body["maxSymbolPositionPct"]), 64)
	if pct == 0 {
		pct = 0.10
	}
	data, err := s.Trade.SaveAutoSettings(r.Context(), userID(r), enabled, ratio, pct)
	if err != nil {
		response.Error(w, err.Error())
		return
	}
	response.Success(w, data)
}

func readJSON(r *http.Request) (map[string]interface{}, error) {
	defer r.Body.Close()
	raw, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		return nil, err
	}
	if len(raw) == 0 {
		return map[string]interface{}{}, nil
	}
	var out map[string]interface{}
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func str(v interface{}) string {
	if v == nil {
		return ""
	}
	switch x := v.(type) {
	case string:
		return x
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case bool:
		if x {
			return "true"
		}
		return "false"
	default:
		return ""
	}
}

func strOr(v interface{}, fallback string) string {
	s := strings.TrimSpace(str(v))
	if s == "" {
		return fallback
	}
	return s
}

func truthy(v interface{}) bool {
	switch x := v.(type) {
	case bool:
		return x
	case string:
		switch strings.ToLower(strings.TrimSpace(x)) {
		case "1", "true", "yes", "on":
			return true
		}
	case float64:
		return x != 0
	}
	return false
}
