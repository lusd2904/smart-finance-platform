package tradeexec

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/longbridge/openapi-go/config"
	lbhttp "github.com/longbridge/openapi-go/http"
	"github.com/longbridge/openapi-go/trade"
	"github.com/shopspring/decimal"
)

// SDKBroker talks to Longbridge via github.com/longbridge/openapi-go.
// Trade calls use HTTP-only TradeContext (no WS). Quotes use the same signed HTTP client.
type SDKBroker struct{}

func NewSDKBroker() *SDKBroker { return &SDKBroker{} }

func buildConfig(creds Creds) (*config.Config, error) {
	if !creds.Configured() {
		return nil, fmt.Errorf("长桥凭据未配置")
	}
	cfg, err := config.New(config.WithConfigKey(creds.AppKey, creds.AppSecret, creds.AccessToken))
	if err != nil {
		return nil, err
	}
	region := strings.ToLower(strings.TrimSpace(creds.Region))
	if region == "" || region == "cn" {
		cfg.Region = config.RegionCN
		cfg.HttpURL = "https://openapi.longbridge.cn"
		cfg.QuoteUrl = "wss://openapi-quote.longbridge.cn"
		cfg.TradeUrl = "wss://openapi-trade.longbridge.cn"
	} else {
		cfg.HttpURL = "https://openapi.longbridge.com"
		cfg.QuoteUrl = "wss://openapi-quote.longbridge.com"
		cfg.TradeUrl = "wss://openapi-trade.longbridge.com"
	}
	cfg.EnableOvernight = true
	return cfg, nil
}

func tradeCtx(creds Creds) (*trade.TradeContext, error) {
	cfg, err := buildConfig(creds)
	if err != nil {
		return nil, err
	}
	return trade.NewHTTPFromCfg(cfg)
}

func decFloat(d *decimal.Decimal) float64 {
	if d == nil {
		return 0
	}
	f, _ := d.Float64()
	return f
}

func parseFloat(s string) float64 {
	s = strings.TrimSpace(s)
	if s == "" {
		return 0
	}
	f, err := strconv.ParseFloat(s, 64)
	if err != nil {
		return 0
	}
	return f
}

func (s *SDKBroker) AccountBalance(ctx context.Context, creds Creds) (Account, error) {
	if !creds.Configured() {
		return Account{Configured: false, Message: "长桥凭据未配置"}, nil
	}
	tctx, err := tradeCtx(creds)
	if err != nil {
		return Account{Configured: true, Reason: "unavailable", Message: err.Error()}, err
	}
	defer tctx.Close()
	rows, err := tctx.AccountBalance(ctx, &trade.GetAccountBalance{})
	if err != nil {
		return Account{Configured: true, Message: "获取账户资金失败: " + err.Error()}, err
	}
	out := Account{Configured: true}
	for _, b := range rows {
		avail := decFloat(b.TotalCash)
		for _, ci := range b.CashInfos {
			if ci == nil {
				continue
			}
			if ci.Currency == "" || ci.Currency == b.Currency {
				if v := decFloat(ci.AvailableCash); v > 0 {
					avail = v
					break
				}
			}
		}
		out.Balances = append(out.Balances, Balance{
			Currency:         b.Currency,
			TotalCash:        decFloat(b.TotalCash),
			AvailableCash:    avail,
			NetAssets:        decFloat(b.NetAssets),
			MaxFinanceAmount: decFloat(b.MaxFinanceAmount),
		})
	}
	return out, nil
}

func (s *SDKBroker) Positions(ctx context.Context, creds Creds) ([]Position, error) {
	if !creds.Configured() {
		return nil, nil
	}
	tctx, err := tradeCtx(creds)
	if err != nil {
		return nil, err
	}
	defer tctx.Close()
	channels, err := tctx.StockPositions(ctx, nil)
	if err != nil {
		return nil, err
	}
	var out []Position
	for _, ch := range channels {
		if ch == nil {
			continue
		}
		for _, p := range ch.Positions {
			if p == nil {
				continue
			}
			out = append(out, Position{
				Symbol:            p.Symbol,
				SymbolName:        p.SymbolName,
				Quantity:          parseFloat(p.Quantity),
				AvailableQuantity: parseFloat(p.AvailableQuantity),
				CostPrice:         decFloat(p.CostPrice),
				Currency:          p.Currency,
			})
		}
	}
	return out, nil
}

func (s *SDKBroker) TodayOrders(ctx context.Context, creds Creds) ([]Order, error) {
	if !creds.Configured() {
		return nil, nil
	}
	tctx, err := tradeCtx(creds)
	if err != nil {
		return nil, err
	}
	defer tctx.Close()
	rows, err := tctx.TodayOrders(ctx, &trade.GetTodayOrders{})
	if err != nil {
		return nil, err
	}
	out := make([]Order, 0, len(rows))
	for _, o := range rows {
		if o == nil {
			continue
		}
		qty := parseFloat(o.Quantity)
		execQty := parseFloat(o.ExecutedQuantity)
		status := string(o.Status)
		out = append(out, Order{
			OrderID:          o.OrderId,
			Symbol:           o.Symbol,
			StockName:        o.StockName,
			Side:             string(o.Side),
			Status:           status,
			StatusLabel:      orderStatusLabel(status),
			OrderType:        string(o.OrderType),
			Quantity:         qty,
			Price:            decFloat(o.Price),
			ExecutedQuantity: execQty,
			ExecutedPrice:    decFloat(o.ExecutedPrice),
			Currency:         o.Currency,
			SubmittedAt:      o.SubmittedAt,
			UpdatedAt:        o.UpdatedAt,
			Remark:           o.Msg,
			Filled:           execQty > 0 && qty > 0 && execQty >= qty,
			Open:             isOpenStatus(status),
		})
	}
	return out, nil
}

type quoteHTTPResp struct {
	List []struct {
		Symbol    string `json:"symbol"`
		LastDone  string `json:"last_done"`
		PrevClose string `json:"prev_close"`
	} `json:"list"`
}

func (s *SDKBroker) RealtimeQuotes(ctx context.Context, creds Creds, symbols []string, market string) ([]Quote, error) {
	if !creds.Configured() || len(symbols) == 0 {
		return nil, nil
	}
	cfg, err := buildConfig(creds)
	if err != nil {
		return nil, err
	}
	client, err := lbhttp.NewFromCfg(cfg)
	if err != nil {
		return nil, err
	}
	normalized := make([]string, 0, len(symbols))
	seen := map[string]struct{}{}
	for _, raw := range symbols {
		lb := ToLongbridgeSymbol(raw, market)
		if lb == "" {
			continue
		}
		if _, ok := seen[lb]; ok {
			continue
		}
		seen[lb] = struct{}{}
		normalized = append(normalized, lb)
	}
	if len(normalized) == 0 {
		return nil, nil
	}
	q := url.Values{}
	q.Set("symbol", strings.Join(normalized, ","))
	var resp quoteHTTPResp
	if err := client.Get(ctx, "/v1/quote/quote", q, &resp); err != nil {
		return nil, err
	}
	out := make([]Quote, 0, len(resp.List))
	for _, row := range resp.List {
		last := parseFloat(row.LastDone)
		out = append(out, Quote{
			Symbol:    row.Symbol,
			LastDone:  last,
			Last:      last,
			PrevClose: parseFloat(row.PrevClose),
		})
	}
	return out, nil
}

func (s *SDKBroker) SubmitOrder(ctx context.Context, creds Creds, req SubmitReq) SubmitResult {
	if !creds.Configured() {
		return SubmitResult{Configured: false, OK: false, Message: "长桥凭据未配置"}
	}
	hasPrice := req.Price > 0
	if msg := ValidateOrderInput(req.Symbol, req.Side, req.Quantity, req.OrderType, req.Price, hasPrice); msg != "" {
		return SubmitResult{Configured: true, OK: false, Message: msg}
	}
	lb := ToLongbridgeSymbol(req.Symbol, req.Market)
	tctx, err := tradeCtx(creds)
	if err != nil {
		return SubmitResult{Configured: true, OK: false, Message: "下单失败: " + err.Error()}
	}
	defer tctx.Close()

	ot := NormalizeOrderType(req.OrderType)
	side := trade.OrderSideBuy
	if NormalizeSide(req.Side) == "sell" {
		side = trade.OrderSideSell
	}
	params := &trade.SubmitOrder{
		Symbol:            lb,
		OrderType:         trade.OrderType(ot),
		Side:              side,
		SubmittedQuantity: uint64(math.Max(1, req.Quantity)),
		TimeInForce:       trade.TimeTypeDay,
	}
	if ot != "MO" {
		params.SubmittedPrice = decimal.NewFromFloat(req.Price)
	}
	outside := ""
	if IsUSListed(lb, req.Market) {
		mode := USOutsideRTHMode(time.Time{})
		if mode == "overnight" {
			params.OutsideRTH = trade.OutsideRTHOvernight
		} else {
			params.OutsideRTH = trade.OutsideRTHAny
		}
		outside = mode
	}
	orderID, err := tctx.SubmitOrder(ctx, params)
	if err != nil {
		return SubmitResult{Configured: true, OK: false, Message: "下单失败: " + err.Error()}
	}
	return SubmitResult{
		Configured: true,
		OK:         true,
		OrderID:    orderID,
		Symbol:     lb,
		OutsideRTH: outside,
		Message:    "下单已提交",
	}
}

func orderStatusLabel(status string) string {
	text := strings.ToLower(strings.ReplaceAll(strings.ReplaceAll(status, "_", ""), " ", ""))
	checks := []struct{ key, label string }{
		{"partialfilled", "部分成交"},
		{"waittocancel", "待撤"},
		{"waittonew", "待报"},
		{"submitted", "已提交"},
		{"cancelled", "已撤"},
		{"canceled", "已撤"},
		{"rejected", "已拒绝"},
		{"expired", "已过期"},
		{"filled", "已成交"},
	}
	for _, c := range checks {
		if strings.Contains(text, c.key) {
			return c.label
		}
	}
	if text == "new" || text == "notreported" {
		return "待成交"
	}
	if status == "" {
		return "--"
	}
	return status
}

func isOpenStatus(status string) bool {
	s := strings.ToLower(status)
	switch s {
	case "submitted", "new", "wait_to_new", "partial_filled", "wait_to_cancel":
		return true
	default:
		return false
	}
}

// HaltState is the Redis sfp:trade:halt payload.
type HaltState struct {
	Halted bool   `json:"halted"`
	Reason string `json:"reason"`
	By     any    `json:"by"`
	At     string `json:"at"`
}

func ParseHalt(raw string) HaltState {
	if strings.TrimSpace(raw) == "" {
		return HaltState{}
	}
	var h HaltState
	if err := json.Unmarshal([]byte(raw), &h); err != nil {
		return HaltState{}
	}
	return h
}

func HaltBlockReason(h HaltState) string {
	if !h.Halted {
		return ""
	}
	extra := strings.TrimSpace(h.Reason)
	if extra != "" {
		return "紧急停机中，禁止新委托：" + extra
	}
	return "紧急停机中，禁止新委托"
}
