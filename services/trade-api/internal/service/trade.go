package service

import (
	"context"
	"encoding/json"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/repo"
	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/redis/go-redis/v9"
)

type Trade struct {
	Broker tradeexec.Broker
	Repo   *repo.Repo
	Redis  *redis.Client
}

func (s *Trade) creds(ctx context.Context, userID int) (tradeexec.Creds, error) {
	return s.Repo.LoadCreds(ctx, userID)
}

func (s *Trade) ReadHalt(ctx context.Context) tradeexec.HaltState {
	raw, err := s.Redis.Get(ctx, tradeexec.HaltRedisKey).Result()
	if err != nil || strings.TrimSpace(raw) == "" {
		return tradeexec.HaltState{}
	}
	return tradeexec.ParseHalt(raw)
}

func (s *Trade) WriteHalt(ctx context.Context, halted bool, reason string, userID int) tradeexec.HaltState {
	payload := tradeexec.HaltState{
		Halted: halted,
		Reason: strings.TrimSpace(reason),
		By:     userID,
		At:     tradeexec.BeijingNow(),
	}
	if halted && payload.Reason == "" {
		payload.Reason = "紧急停机"
	}
	b, _ := json.Marshal(payload)
	_ = s.Redis.Set(ctx, tradeexec.HaltRedisKey, string(b), 0).Err()
	return payload
}

func (s *Trade) Account(ctx context.Context, userID int) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	acc, err := s.Broker.AccountBalance(ctx, creds)
	if err != nil {
		return nil, err
	}
	return tradeexec.FlattenAccount(acc), nil
}

func (s *Trade) Positions(ctx context.Context, userID int) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	if !creds.Configured() {
		return map[string]interface{}{"configured": false, "message": "长桥凭据未配置", "positions": []interface{}{}}, nil
	}
	positions, err := s.Broker.Positions(ctx, creds)
	if err != nil {
		return nil, err
	}
	symbols := make([]string, 0, len(positions))
	for _, p := range positions {
		if p.Symbol != "" {
			symbols = append(symbols, p.Symbol)
		}
	}
	quotes, _ := s.Broker.RealtimeQuotes(ctx, creds, symbols, "US")
	return map[string]interface{}{
		"configured":   true,
		"positions":    tradeexec.MergePositionQuotes(positions, quotes),
		"quotesSource": "longbridge",
	}, nil
}

func (s *Trade) Orders(ctx context.Context, userID int, scope string) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	if !creds.Configured() {
		return map[string]interface{}{"configured": false, "message": "长桥凭据未配置", "orders": []interface{}{}}, nil
	}
	var orders []tradeexec.Order
	if strings.EqualFold(scope, "history") {
		orders, err = s.Broker.HistoryOrders(ctx, creds, 100)
	} else {
		orders, err = s.Broker.TodayOrders(ctx, creds)
	}
	if err != nil {
		return nil, err
	}
	return tradeexec.OrdersPayload(orders), nil
}

func (s *Trade) OrderDetail(ctx context.Context, userID int, orderID string) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	if !creds.Configured() {
		return map[string]interface{}{"configured": false, "ok": false, "message": "长桥凭据未配置", "order": nil}, nil
	}
	order, scope, found, err := s.Broker.FindOrder(ctx, creds, orderID)
	if err != nil {
		return nil, err
	}
	if !found {
		return map[string]interface{}{"configured": true, "ok": false, "message": "未找到该订单", "order": nil}, nil
	}
	return map[string]interface{}{
		"configured": true,
		"ok":         true,
		"scope":      scope,
		"order":      tradeexec.OrderToMap(order),
	}, nil
}

func (s *Trade) RealtimeQuotes(ctx context.Context, userID int, symbols []string, market string) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	if !creds.Configured() {
		return map[string]interface{}{"configured": false, "quotes": []interface{}{}, "message": "长桥凭据未配置"}, nil
	}
	if len(symbols) == 0 {
		return map[string]interface{}{"configured": true, "quotes": []interface{}{}, "message": "标的列表为空"}, nil
	}
	quotes, err := s.Broker.RealtimeQuotes(ctx, creds, symbols, market)
	if err != nil {
		return nil, err
	}
	items := make([]map[string]interface{}, 0, len(quotes))
	for _, q := range quotes {
		last := q.LastDone
		if last == 0 {
			last = q.Last
		}
		items = append(items, map[string]interface{}{
			"symbol":    q.Symbol,
			"lastDone":  last,
			"last":      last,
			"prevClose": q.PrevClose,
		})
	}
	return map[string]interface{}{"configured": true, "quotes": items}, nil
}

type SubmitInput struct {
	Symbol    string
	Side      string
	Quantity  float64
	OrderType string
	Price     float64
	HasPrice  bool
	Market    string
}

func (s *Trade) SubmitOrder(ctx context.Context, userID int, in SubmitInput) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	settings := s.Repo.LoadSettings(ctx, userID)
	halt := s.ReadHalt(ctx)
	snap, err := tradeexec.LoadBrokerSnapshot(ctx, s.Broker, creds)
	if err != nil {
		return nil, err
	}
	fx := tradeexec.NewFxRates()
	last := in.Price
	if last <= 0 {
		quotes, _ := s.Broker.RealtimeQuotes(ctx, creds, []string{in.Symbol}, in.Market)
		last = tradeexec.ExtractLastPrice(quotes, in.Symbol)
	}
	eval := tradeexec.EvaluateManualOrder(snap.Account, snap.Positions, snap.TodayOrders, tradeexec.ManualEvalInput{
		Symbol: in.Symbol, Side: in.Side, Quantity: in.Quantity, Price: in.Price, Market: in.Market,
		Settings: settings, Fx: fx, Halted: halt,
	}, last)
	if !eval.OK {
		return map[string]interface{}{
			"configured": creds.Configured(),
			"ok":         false,
			"blocked":    true,
			"message":    eval.Message,
			"reason":     eval.Reason,
		}, nil
	}
	res := s.Broker.SubmitOrder(ctx, creds, tradeexec.SubmitReq{
		Symbol: in.Symbol, Side: in.Side, Quantity: in.Quantity,
		OrderType: in.OrderType, Price: in.Price, Market: in.Market,
	})
	out := map[string]interface{}{
		"configured": res.Configured,
		"ok":         res.OK,
		"message":    res.Message,
	}
	if res.OrderID != "" {
		out["orderId"] = res.OrderID
	}
	if res.Symbol != "" {
		out["symbol"] = res.Symbol
	}
	if res.OutsideRTH != "" {
		out["outsideRth"] = res.OutsideRTH
	}
	return out, nil
}

func (s *Trade) CancelOrder(ctx context.Context, userID int, orderID string) (map[string]interface{}, error) {
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	ok, msg := s.Broker.CancelOrder(ctx, creds, orderID)
	return map[string]interface{}{"configured": creds.Configured(), "ok": ok, "message": msg}, nil
}

func (s *Trade) AutoStatus(ctx context.Context, userID int) (map[string]interface{}, error) {
	settings := s.Repo.LoadSettings(ctx, userID)
	creds, err := s.creds(ctx, userID)
	if err != nil {
		return nil, err
	}
	configured := creds.Configured()
	halt := s.ReadHalt(ctx)
	submitAllowed, submitReason := tradeexec.ResolveSubmitPermission(true, configured, settings.AutoTradeEnabled)
	if block := tradeexec.HaltBlockReason(halt); block != "" {
		submitAllowed = false
		submitReason = block
	}
	fx := tradeexec.NewFxRates()
	netAssets := 0.0
	if configured {
		acc, err := s.Broker.AccountBalance(ctx, creds)
		if err == nil {
			netAssets = tradeexec.PickNetAssets(acc, fx)
		}
	}
	maxDaily := tradeexec.DailyBuyCap(netAssets, settings.DailyBuyRatio)
	maxSymbol := tradeexec.SymbolPositionCap(netAssets, settings.MaxSymbolPositionPct)
	todayOrders := 0
	todayNotional := 0.0
	if configured {
		orders, err := s.Broker.TodayOrders(ctx, creds)
		if err == nil {
			todayOrders, todayNotional = tradeexec.TodayBuyNotionalFromOrders(orders)
		}
	}
	msg := ""
	if !configured {
		msg = "长桥凭据未配置，自动交易仅扫描、不会下单"
	} else if !settings.AutoTradeEnabled {
		msg = "自动交易未开启，仅扫描不下单"
	}
	return map[string]interface{}{
		"configured":         configured,
		"message":            msg,
		"autoTradeEnabled":   settings.AutoTradeEnabled,
		"submitAllowed":      submitAllowed,
		"submitBlockReason":  submitReason,
		"guardrails": map[string]interface{}{
			"todayOrdersCount":        todayOrders,
			"maxDailyOrders":          10,
			"todayNotionalAmount":     todayNotional,
			"maxDailyNotionalAmount":  maxDaily,
			"dailyBuyRatio":           settings.DailyBuyRatio,
			"maxSymbolPositionPct":    settings.MaxSymbolPositionPct,
			"maxPerSymbolNotional":    maxSymbol,
			"halted":                  halt.Halted,
			"isOrderLimitReached":     todayOrders >= 10,
			"isAmountLimitReached":    todayNotional >= maxDaily,
		},
		"config": map[string]interface{}{
			"autoTradeEnabled":      settings.AutoTradeEnabled,
			"dailyBuyRatio":         settings.DailyBuyRatio,
			"maxSymbolPositionPct":  settings.MaxSymbolPositionPct,
		},
	}, nil
}

func (s *Trade) SaveAutoSettings(ctx context.Context, userID int, enabled bool, dailyBuyRatio, maxSymbolPct float64) (map[string]interface{}, error) {
	if err := s.Repo.SaveAutoSettings(ctx, userID, enabled, dailyBuyRatio, maxSymbolPct); err != nil {
		return nil, err
	}
	return s.AutoStatus(ctx, userID)
}
