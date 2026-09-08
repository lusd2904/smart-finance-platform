package market

import (
	"fmt"
	"sort"
	"strings"
)

const (
	CandidateCap        = 80
	PicksPerMarket      = 10
	AIPerMarket         = 10
	BuyScoreThreshold   = 62.0
	WatchScoreThreshold = 58.0
)

var SentimentField = map[string]string{
	"US": "usScore",
	"HK": "hkScore",
	"CN": "aScore",
}

type Candidate struct {
	Symbol   string
	Name     string
	Market   string
	Category string
}

func ClampScore(value *float64, defaultVal float64) float64 {
	if value == nil {
		return defaultVal
	}
	if *value < 0 {
		return 0
	}
	if *value > 100 {
		return 100
	}
	return *value
}

func NormalizeSentiment(raw *float64) float64 {
	if raw == nil {
		return 50
	}
	return ClampScore(&[]float64{(*raw + 10) * 5}[0], 50)
}

func IsIndexSymbol(symbol, category string) bool {
	code := strings.TrimSpace(symbol)
	if code == "" {
		return true
	}
	if strings.EqualFold(category, "index") {
		return true
	}
	return strings.HasPrefix(code, "^")
}

func MergeCandidates(top50, featured []Candidate, cap int) []Candidate {
	if cap <= 0 {
		cap = CandidateCap
	}
	seen := map[string]bool{}
	out := []Candidate{}
	for _, row := range append(top50, featured...) {
		symbol := strings.TrimSpace(row.Symbol)
		mkt := strings.ToUpper(strings.TrimSpace(row.Market))
		if mkt == "" {
			mkt = "US"
		}
		if IsIndexSymbol(symbol, row.Category) || (mkt != "US" && mkt != "HK" && mkt != "CN") {
			continue
		}
		key := strings.ToUpper(symbol) + "|" + mkt
		if seen[key] {
			continue
		}
		seen[key] = true
		name := strings.TrimSpace(row.Name)
		if name == "" {
			name = symbol
		}
		out = append(out, Candidate{Symbol: symbol, Name: name, Market: mkt, Category: row.Category})
		if len(out) >= cap {
			break
		}
	}
	return out
}

func CombinePickScore(factorTotal *float64, sentimentRaw, heatScore, indexChange *float64, indexOpen bool) float64 {
	factor := ClampScore(factorTotal, 0)
	sent := NormalizeSentiment(sentimentRaw)
	if !indexOpen {
		return round2(0.72*factor + 0.28*sent)
	}
	heat := ClampScore(heatScore, 50)
	idx := 50.0
	if indexChange != nil {
		idx = ClampScore(&[]float64{50 + *indexChange*8}[0], 50)
	}
	return round2(0.55*factor + 0.20*sent + 0.15*heat + 0.10*idx)
}

func RecoFromSignal(signal string, pickScore float64) (string, string) {
	sig := strings.ToUpper(strings.TrimSpace(signal))
	if sig == "" {
		sig = "HOLD"
	}
	switch {
	case sig == "BUY" && pickScore >= BuyScoreThreshold:
		return "买入", "偏多"
	case sig == "BUY":
		return "关注", "偏多"
	case sig == "SELL":
		return "回避", "偏空"
	case pickScore >= WatchScoreThreshold:
		return "关注", "偏多"
	default:
		return "观望", "中性"
	}
}

func SelectTopPicks(rows []map[string]interface{}, perMarket int) []map[string]interface{} {
	if perMarket <= 0 {
		perMarket = PicksPerMarket
	}
	buckets := map[string][]map[string]interface{}{"US": {}, "HK": {}, "CN": {}}
	for _, row := range rows {
		mkt := strings.ToUpper(stringFrom(row["market"]))
		if _, ok := buckets[mkt]; ok {
			buckets[mkt] = append(buckets[mkt], row)
		}
	}
	picked := []map[string]interface{}{}
	marketOrder := []string{"CN", "HK", "US"}
	for _, mkt := range marketOrder {
		items := buckets[mkt]
		sort.Slice(items, func(i, j int) bool {
			si := 0
			if strings.ToUpper(stringFrom(items[i]["signal"])) == "BUY" {
				si = 1
			}
			sj := 0
			if strings.ToUpper(stringFrom(items[j]["signal"])) == "BUY" {
				sj = 1
			}
			if si != sj {
				return si > sj
			}
			return floatFrom(items[i]["pickScore"]) > floatFrom(items[j]["pickScore"])
		})
		for rank, item := range items {
			if rank >= perMarket {
				break
			}
			row := map[string]interface{}{}
			for k, v := range item {
				row[k] = v
			}
			row["rankNo"] = rank + 1
			row["market"] = mkt
			picked = append(picked, row)
		}
	}
	sort.Slice(picked, func(i, j int) bool {
		order := map[string]int{"CN": 0, "HK": 1, "US": 2}
		mi := order[stringFrom(picked[i]["market"])]
		mj := order[stringFrom(picked[j]["market"])]
		if mi != mj {
			return mi < mj
		}
		return intFrom(picked[i]["rankNo"]) < intFrom(picked[j]["rankNo"])
	})
	return picked
}

func ApplyAIResult(row map[string]interface{}, parsed map[string]interface{}) {
	if parsed == nil {
		return
	}
	row["source"] = "ai"
	if v := parsed["stance"]; v != nil && v != "" {
		row["stance"] = v
	}
	if v := parsed["recommendation"]; v != nil && v != "" {
		row["recommendation"] = v
	}
	if v := parsed["confidence"]; v != nil {
		row["confidence"] = clampInt(v, 0, 100)
	}
	if v := parsed["summary"]; v != nil && v != "" {
		row["summary"] = v
	}
	if v := parsed["indicator_review"]; v != nil && v != "" {
		row["indicatorReview"] = v
	}
	if v := parsed["sentiment_review"]; v != nil && v != "" {
		row["sentimentReview"] = v
	}
	if v := parsed["operation_advice"]; v != nil && v != "" {
		row["operationAdvice"] = v
	}
	if v := parsed["risk_warning"]; v != nil && v != "" {
		row["riskWarning"] = v
	}
}

func stringFrom(v interface{}) string {
	if v == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprint(v))
}

func floatFrom(v interface{}) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case float32:
		return float64(n)
	case int:
		return float64(n)
	case int64:
		return float64(n)
	default:
		return 0
	}
}

func intFrom(v interface{}) int {
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	default:
		return 0
	}
}

func clampInt(v interface{}, lo, hi int) int {
	n := intFrom(v)
	if n < lo {
		return lo
	}
	if n > hi {
		return hi
	}
	return n
}

func round2(v float64) float64 {
	return float64(int(v*100+0.5)) / 100
}
