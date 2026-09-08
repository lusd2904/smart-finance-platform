package tradeexec

import (
	"context"
	"strings"
	"time"

	"github.com/longbridge/openapi-go/quote"
)

const cnNoDepthMsg = "A股盘口请使用时序库"

func quoteCtx(creds Creds) (*quote.QuoteContext, error) {
	cfg, err := buildConfig(creds)
	if err != nil {
		return nil, err
	}
	return quote.NewFromCfg(cfg)
}

func (s *SDKBroker) GetDepth(ctx context.Context, creds Creds, symbol, market string) map[string]interface{} {
	code, mkt := ParseSymbolMarket(symbol, market)
	if IsCNMarket(mkt, code) {
		return emptyDepth(code, mkt, creds.Configured(), "cn_no_depth", cnNoDepthMsg, "")
	}
	if !creds.Configured() {
		return emptyDepth(code, mkt, false, "unconfigured", "长桥凭据未配置，盘口暂不可用", "")
	}
	lb := ToLongbridgeSymbol(code, mkt)
	qctx, err := quoteCtx(creds)
	if err != nil {
		return emptyDepth(code, mkt, true, "unavailable", err.Error(), lb)
	}
	defer qctx.Close()
	raw, err := qctx.Depth(ctx, lb)
	if err != nil {
		return emptyDepth(code, mkt, true, "error", "盘口暂不可用: "+err.Error(), lb)
	}
	return assembleDepth(raw, code, mkt, lb)
}

func (s *SDKBroker) GetTrades(ctx context.Context, creds Creds, symbol, market string, count int) map[string]interface{} {
	code, mkt := ParseSymbolMarket(symbol, market)
	count = quoteClampInt(count, 1, 100, 30)
	if IsCNMarket(mkt, code) {
		return emptyTrades(code, mkt, creds.Configured(), "cn_no_depth", cnNoDepthMsg, "")
	}
	if !creds.Configured() {
		return emptyTrades(code, mkt, false, "unconfigured", "长桥凭据未配置，成交明细暂不可用", "")
	}
	lb := ToLongbridgeSymbol(code, mkt)
	qctx, err := quoteCtx(creds)
	if err != nil {
		return emptyTrades(code, mkt, true, "unavailable", err.Error(), lb)
	}
	defer qctx.Close()
	raw, err := qctx.Trades(ctx, lb, int32(count))
	if err != nil {
		return emptyTrades(code, mkt, true, "error", "成交明细暂不可用: "+err.Error(), lb)
	}
	return assembleTrades(raw, code, mkt, lb, count)
}

func (s *SDKBroker) GetCandlesticks(ctx context.Context, creds Creds, symbol, market, period string, count int) map[string]interface{} {
	code, mkt := ParseSymbolMarket(symbol, market)
	count = quoteClampInt(count, 1, 1000, 200)
	if IsCNMarket(mkt, code) {
		return emptyKlines(code, mkt, period, creds.Configured(), "cn_no_depth", "A股K线请使用时序库")
	}
	if !creds.Configured() {
		return emptyKlines(code, mkt, period, false, "unconfigured", "长桥凭据未配置")
	}
	lb := ToLongbridgeSymbol(code, mkt)
	qctx, err := quoteCtx(creds)
	if err != nil {
		return emptyKlines(code, mkt, period, true, "unavailable", err.Error())
	}
	defer qctx.Close()
	periodEnum := resolveLBPeriod(period)
	if periodEnum == 0 {
		return emptyKlines(code, mkt, period, true, "unavailable", "长桥 candlesticks 不可用或周期不支持")
	}
	sticks, err := qctx.Candlesticks(ctx, lb, periodEnum, int32(count), quote.AdjustTypeNo)
	if err != nil {
		return emptyKlines(code, mkt, period, true, "error", "长桥K线暂不可用: "+err.Error())
	}
	withTime := !isDailyPeriod(period)
	tz := klineTZ(mkt)
	klines := make([]map[string]interface{}, 0, len(sticks))
	for _, bar := range sticks {
		row := mapCandlestick(bar, withTime, tz)
		if row["close"] == nil {
			continue
		}
		klines = append(klines, row)
	}
	return map[string]interface{}{
		"configured": true,
		"available":  len(klines) > 0,
		"symbol":     code,
		"market":     strings.ToUpper(mkt),
		"lbSymbol":   lb,
		"period":     period,
		"klines":     klines,
	}
}

func (s *SDKBroker) GetIntraday(ctx context.Context, creds Creds, symbol, market string) map[string]interface{} {
	code, mkt := ParseSymbolMarket(symbol, market)
	if IsCNMarket(mkt, code) {
		return emptyKlines(code, mkt, "intraday", creds.Configured(), "cn_no_depth", "A股分时请使用时序库")
	}
	if !creds.Configured() {
		return emptyKlines(code, mkt, "intraday", false, "unconfigured", "长桥凭据未配置")
	}
	lb := ToLongbridgeSymbol(code, mkt)
	qctx, err := quoteCtx(creds)
	if err != nil {
		return emptyKlines(code, mkt, "intraday", true, "unavailable", err.Error())
	}
	defer qctx.Close()
	lines, err := qctx.Intraday(ctx, lb)
	if err != nil {
		return emptyKlines(code, mkt, "intraday", true, "error", "分时暂不可用: "+err.Error())
	}
	tz := klineTZ(mkt)
	klines := make([]map[string]interface{}, 0, len(lines))
	for _, pt := range lines {
		klines = append(klines, mapIntradayPoint(pt, tz))
	}
	return map[string]interface{}{
		"configured": true,
		"available":  len(klines) > 0,
		"symbol":     code,
		"market":     strings.ToUpper(mkt),
		"lbSymbol":   lb,
		"period":     "intraday",
		"klines":     klines,
	}
}

func (s *SDKBroker) GetQuoteSnapshot(ctx context.Context, creds Creds, symbol, market string) map[string]interface{} {
	code, mkt := ParseSymbolMarket(symbol, market)
	lb := ToLongbridgeSymbol(code, mkt)
	base := map[string]interface{}{
		"configured": creds.Configured(),
		"available":  false,
		"symbol":     code,
		"market":     strings.ToUpper(mkt),
		"lbSymbol":   lb,
	}
	if IsCNMarket(mkt, code) {
		base["reason"] = "cn_no_depth"
		base["message"] = "A股基本面请使用时序库/标的库"
		return base
	}
	if !creds.Configured() {
		base["reason"] = "unconfigured"
		base["message"] = "长桥凭据未配置"
		return base
	}
	qctx, err := quoteCtx(creds)
	if err != nil {
		base["reason"] = "unavailable"
		base["message"] = err.Error()
		return base
	}
	defer qctx.Close()

	quoteMap := map[string]interface{}{}
	if rows, qerr := qctx.Quote(ctx, []string{lb}); qerr == nil && len(rows) > 0 {
		quoteMap = mapSecurityQuote(rows[0])
	}
	staticMap := map[string]interface{}{}
	if rows, serr := qctx.StaticInfo(ctx, []string{lb}); serr == nil && len(rows) > 0 {
		staticMap = mapStaticInfo(rows[0])
	}
	calcMap := map[string]interface{}{}
	indexes := []quote.CalcIndex{
		quote.CalcIndexPeTTMRatio,
		quote.CalcIndexPbRatio,
		quote.CalcIndexTurnoverRate,
		quote.CalcIndexVolumeRatio,
		quote.CalcIndexTotalMarketValue,
	}
	if rows, cerr := qctx.CalcIndex(ctx, []string{lb}, indexes); cerr == nil && len(rows) > 0 {
		calcMap = mapCalcIndex(rows[0])
	}
	capitalMap := map[string]interface{}{}
	if cap, kerr := qctx.CapitalDistribution(ctx, lb); kerr == nil {
		capitalMap = mapCapitalDistribution(cap)
	}

	out := assembleQuoteSnapshot(code, mkt, lb, quoteMap, staticMap, calcMap, capitalMap)
	out["configured"] = true
	out["news"] = []interface{}{}
	return out
}

func emptyDepth(symbol, market string, configured bool, reason, message, lb string) map[string]interface{} {
	mkt := strings.ToUpper(market)
	if IsCNMarket(market, symbol) {
		mkt = "CN"
	}
	data := map[string]interface{}{
		"configured": configured, "available": false, "reason": reason, "message": message,
		"symbol": symbol, "market": mkt, "asks": []interface{}{}, "bids": []interface{}{}, "last": nil,
	}
	if lb != "" {
		data["lbSymbol"] = lb
	}
	return data
}

func emptyTrades(symbol, market string, configured bool, reason, message, lb string) map[string]interface{} {
	mkt := strings.ToUpper(market)
	if IsCNMarket(market, symbol) {
		mkt = "CN"
	}
	data := map[string]interface{}{
		"configured": configured, "available": false, "reason": reason, "message": message,
		"symbol": symbol, "market": mkt, "trades": []interface{}{},
	}
	if lb != "" {
		data["lbSymbol"] = lb
	}
	return data
}

func emptyKlines(symbol, market, period string, configured bool, reason, message string) map[string]interface{} {
	mkt := strings.ToUpper(market)
	if IsCNMarket(market, symbol) {
		mkt = "CN"
	}
	return map[string]interface{}{
		"configured": configured, "available": false, "reason": reason, "message": message,
		"symbol": symbol, "market": mkt, "period": period, "klines": []interface{}{},
	}
}

func assembleDepth(raw *quote.SecurityDepth, symbol, market, lb string) map[string]interface{} {
	asks := make([]map[string]interface{}, 0)
	bids := make([]map[string]interface{}, 0)
	if raw != nil {
		for _, x := range raw.Ask {
			if x == nil {
				continue
			}
			row := mapDepthLevel(x)
			row["side"] = "ask"
			if row["price"] != nil {
				asks = append(asks, row)
			}
		}
		for _, x := range raw.Bid {
			if x == nil {
				continue
			}
			row := mapDepthLevel(x)
			row["side"] = "bid"
			if row["price"] != nil {
				bids = append(bids, row)
			}
		}
	}
	if len(asks) > 10 {
		asks = asks[:10]
	}
	if len(bids) > 10 {
		bids = bids[:10]
	}
	msg := interface{}(nil)
	reason := interface{}(nil)
	if len(asks) == 0 && len(bids) == 0 {
		msg = "暂无盘口"
		reason = "empty"
	}
	return map[string]interface{}{
		"configured": true, "available": len(asks) > 0 || len(bids) > 0,
		"reason": reason, "message": msg,
		"symbol": symbol, "market": strings.ToUpper(market), "lbSymbol": lb,
		"asks": asks, "bids": bids, "last": nil,
	}
}

func assembleTrades(raw []*quote.Trade, symbol, market, lb string, count int) map[string]interface{} {
	items := make([]map[string]interface{}, 0, len(raw))
	for _, t := range raw {
		if t == nil {
			continue
		}
		row := mapTrade(t)
		if row["price"] == nil {
			continue
		}
		items = append(items, row)
	}
	if len(items) > count {
		items = items[:count]
	}
	msg := interface{}(nil)
	reason := interface{}(nil)
	if len(items) == 0 {
		msg = "暂无成交"
		reason = "empty"
	}
	return map[string]interface{}{
		"configured": true, "available": len(items) > 0,
		"reason": reason, "message": msg,
		"symbol": symbol, "market": strings.ToUpper(market), "lbSymbol": lb, "trades": items,
	}
}

func mapDepthLevel(x *quote.Depth) map[string]interface{} {
	return map[string]interface{}{
		"position": x.Position, "price": decFloat(x.Price), "volume": float64(x.Volume),
		"size": float64(x.Volume), "orderNum": float64(x.OrderNum),
	}
}

func mapTrade(t *quote.Trade) map[string]interface{} {
	price := parseFloat(t.Price)
	return map[string]interface{}{
		"time": fmtTradeTime(t.Timestamp), "price": price,
		"volume": float64(t.Volume), "size": float64(t.Volume),
		"side": mapTradeSide(t.Direction), "tradeType": t.TradeType,
	}
}

func mapTradeSide(direction int32) interface{} {
	switch direction {
	case 1:
		return "sell"
	case 2:
		return "buy"
	case 0:
		return "neutral"
	default:
		return nil
	}
}

func mapCandlestick(bar *quote.Candlestick, withTime bool, tz string) map[string]interface{} {
	if bar == nil {
		return map[string]interface{}{}
	}
	return map[string]interface{}{
		"date": fmtBarTime(bar.Timestamp, withTime, tz),
		"open": decFloat(bar.Open), "high": decFloat(bar.High),
		"low": decFloat(bar.Low), "close": decFloat(bar.Close), "volume": float64(bar.Volume),
	}
}

func mapIntradayPoint(pt *quote.IntradayLine, tz string) map[string]interface{} {
	if pt == nil {
		return map[string]interface{}{}
	}
	price := decFloat(pt.Price)
	return map[string]interface{}{
		"date": fmtBarTime(pt.Timestamp, true, tz),
		"open": price, "high": price, "low": price, "close": price, "volume": float64(pt.Volume),
	}
}

func mapSecurityQuote(q *quote.SecurityQuote) map[string]interface{} {
	if q == nil {
		return map[string]interface{}{}
	}
	last := decFloat(q.LastDone)
	return map[string]interface{}{
		"symbol": q.Symbol, "lastDone": last, "last": last,
		"prevClose": decFloat(q.PrevClose), "open": decFloat(q.Open),
		"high": decFloat(q.High), "low": decFloat(q.Low), "volume": float64(q.Volume),
		"turnover": decFloat(q.Turnover),
	}
}

func mapStaticInfo(info *quote.StaticInfo) map[string]interface{} {
	if info == nil {
		return map[string]interface{}{}
	}
	name := info.NameCn
	if name == "" {
		name = info.NameEn
	}
	return map[string]interface{}{
		"symbol": info.Symbol, "name": name, "exchange": info.Exchange,
		"currency": info.Currency, "lotSize": info.LotSize,
		"totalShares": float64(info.TotalShares), "circulatingShares": float64(info.CirculatingShares),
		"eps": decFloat(info.Eps), "dividendYield": info.DividendYield,
	}
}

func mapCalcIndex(idx *quote.SecurityCalcIndex) map[string]interface{} {
	if idx == nil {
		return map[string]interface{}{}
	}
	return map[string]interface{}{
		"peTtm": decFloat(idx.PeTtmRatio), "pb": decFloat(idx.PbRatio),
		"turnoverRate": decFloat(idx.TurnoverRate), "volumeRatio": decFloat(idx.VolumeRatio),
		"totalMarketValue": decFloat(idx.TotalMarketValue),
	}
}

func mapCapitalDistribution(cap quote.CapitalDistribution) map[string]interface{} {
	return map[string]interface{}{
		"capitalInBig": decFloat(cap.CapitalIn.Large), "capitalInMid": decFloat(cap.CapitalIn.Medium),
		"capitalInSmall": decFloat(cap.CapitalIn.Small), "capitalOutBig": decFloat(cap.CapitalOut.Large),
		"capitalOutMid": decFloat(cap.CapitalOut.Medium), "capitalOutSmall": decFloat(cap.CapitalOut.Small),
	}
}

func assembleQuoteSnapshot(symbol, market, lb string, q, static, calc, capital map[string]interface{}) map[string]interface{} {
	out := map[string]interface{}{
		"configured": true, "available": len(q) > 0,
		"symbol": symbol, "market": strings.ToUpper(market), "lbSymbol": lb,
	}
	for k, v := range q {
		out[k] = v
	}
	for k, v := range static {
		if _, ok := out[k]; !ok {
			out[k] = v
		}
	}
	for k, v := range calc {
		out[k] = v
	}
	if len(capital) > 0 {
		out["capitalDistribution"] = capital
	}
	return out
}

func resolveLBPeriod(period string) quote.Period {
	switch strings.ToLower(strings.TrimSpace(period)) {
	case "1min", "1m":
		return quote.PeriodOneMinute
	case "5min", "5m":
		return quote.PeriodFiveMinute
	case "15min", "15m":
		return quote.PeriodFifteenMinute
	case "30min", "30m":
		return quote.PeriodThirtyMinute
	case "60min", "60m", "1h":
		return quote.PeriodSixtyMinute
	case "daily", "day", "d", "1d":
		return quote.PeriodDay
	case "weekly", "week", "w":
		return quote.PeriodWeek
	case "monthly", "month":
		return quote.PeriodMonth
	default:
		return 0
	}
}

func isDailyPeriod(period string) bool {
	switch strings.ToLower(strings.TrimSpace(period)) {
	case "daily", "day", "d", "1d", "weekly", "week", "w", "monthly", "month":
		return true
	default:
		return false
	}
}

func klineTZ(market string) string {
	if strings.ToUpper(market) == "US" {
		return "America/New_York"
	}
	return "Asia/Shanghai"
}

func fmtBarTime(ts int64, withTime bool, tzName string) string {
	if ts <= 0 {
		return ""
	}
	loc := time.Local
	if tzName != "" {
		if l, err := time.LoadLocation(tzName); err == nil {
			loc = l
		}
	}
	t := time.Unix(ts, 0).In(loc)
	if withTime {
		return t.Format("2006-01-02 15:04")
	}
	return t.Format("2006-01-02")
}

func fmtTradeTime(ts int64) string {
	if ts <= 0 {
		return ""
	}
	return time.Unix(ts, 0).In(time.FixedZone("CST", 8*3600)).Format("2006-01-02 15:04:05")
}

func quoteClampInt(v, lo, hi, fallback int) int {
	if v <= 0 {
		v = fallback
	}
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
