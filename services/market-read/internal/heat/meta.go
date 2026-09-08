package heat

import "strings"

type MarketInfo struct {
	Label        string
	Currency     string
	IndexSymbol  string
	IndexName    string
	CapRule      string
	Timezone     string
}

var MarketMeta = map[string]MarketInfo{
	"US": {Label: "美股", Currency: "USD", IndexSymbol: "^GSPC", IndexName: "标普500", CapRule: "10亿-1000亿美元", Timezone: "America/New_York"},
	"HK": {Label: "港股", Currency: "HKD", IndexSymbol: "HSI.HK", IndexName: "恒生指数", CapRule: "100亿-1000亿港币", Timezone: "Asia/Hong_Kong"},
	"CN": {Label: "A股", Currency: "CNY", IndexSymbol: "000001", IndexName: "上证指数", CapRule: "100亿-2000亿人民币", Timezone: "Asia/Shanghai"},
}

var WeightConfigKeys = map[string]string{
	"market.heat.weight.index":            "index",
	"market.heat.weight.turnover":         "turnover",
	"market.heat.weight.advance_decline":  "advance_decline",
}

var DefaultWeights = map[string]float64{
	"index": 0.4, "turnover": 0.3, "advance_decline": 0.3,
}

func NormalizeMarket(market string) (string, error) {
	code := strings.ToUpper(strings.TrimSpace(market))
	if code == "" {
		code = "US"
	}
	if _, ok := MarketMeta[code]; !ok {
		return "", errUnsupportedMarket(code)
	}
	return code, nil
}

type unsupportedMarketError string

func (e unsupportedMarketError) Error() string { return "不支持的市场: " + string(e) }
func errUnsupportedMarket(m string) error { return unsupportedMarketError(m) }
