package heat

import (
	"fmt"
	"strings"
	"time"
)

type MarketInfo struct {
	Label       string
	Currency    string
	IndexSymbol string
	IndexName   string
	CapMin      float64
	CapMax      float64
	CapRule     string
	Timezone    string
}

var MarketMeta = map[string]MarketInfo{
	"US": {Label: "美股", Currency: "USD", IndexSymbol: "^GSPC", IndexName: "标普500", CapMin: 1e9, CapMax: 100e9, CapRule: "10亿-1000亿美元", Timezone: "America/New_York"},
	"HK": {Label: "港股", Currency: "HKD", IndexSymbol: "HSI.HK", IndexName: "恒生指数", CapMin: 10e9, CapMax: 100e9, CapRule: "100亿-1000亿港币", Timezone: "Asia/Hong_Kong"},
	"CN": {Label: "A股", Currency: "CNY", IndexSymbol: "000001", IndexName: "上证指数", CapMin: 10e9, CapMax: 200e9, CapRule: "100亿-2000亿人民币", Timezone: "Asia/Shanghai"},
}

var WeightConfigKeys = map[string]string{
	"market.heat.weight.index":           "index",
	"market.heat.weight.turnover":        "turnover",
	"market.heat.weight.advance_decline": "advance_decline",
}

func DefaultWeights() map[string]float64 {
	return map[string]float64{"index": 0.4, "turnover": 0.3, "advance_decline": 0.3}
}

func NormalizeWeights(weights map[string]float64) map[string]float64 {
	total := 0.0
	for _, v := range weights {
		total += v
	}
	if total <= 0 {
		total = 1
	}
	out := map[string]float64{}
	for k, v := range weights {
		out[k] = round4(v / total)
	}
	return out
}

func NormalizeMarket(market string) (string, error) {
	code := strings.ToUpper(strings.TrimSpace(market))
	if code == "" {
		code = "US"
	}
	if _, ok := MarketMeta[code]; !ok {
		return "", fmt.Errorf("不支持的市场: %s", market)
	}
	return code, nil
}

func TodayInMarket(market string, now time.Time) string {
	meta := MarketMeta[market]
	loc, err := time.LoadLocation(meta.Timezone)
	if err != nil {
		loc = time.FixedZone("CST", 8*3600)
	}
	return now.In(loc).Format("2006-01-02")
}

func ResolveTradeDate(market, tradeDate string, now time.Time) string {
	if len(tradeDate) >= 10 {
		return tradeDate[:10]
	}
	return TodayInMarket(market, now)
}

func IsWeekday(dateStr string) bool {
	dt, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		return false
	}
	return dt.Weekday() != time.Saturday && dt.Weekday() != time.Sunday
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}
