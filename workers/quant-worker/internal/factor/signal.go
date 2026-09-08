package factor

import (
	"fmt"
	"math"
	"strings"
)

var profileThresholds = map[string]struct {
	Buy     float64
	Sell    float64
	MaxRisk string
}{
	"conservative": {72, 42, "medium"},
	"balanced":     {64, 38, "high"},
	"aggressive":   {56, 32, "high"},
}

var riskRank = map[string]int{"low": 0, "medium": 1, "high": 2}

type Decision struct {
	Signal     string
	Confidence int
	Reason     string
}

func DecideSignal(score Score, profile string, custom map[string]any) Decision {
	profile = NormalizeProfile(profile)
	th := profileThresholds[profile]
	if custom != nil {
		if v, ok := floatFrom(custom, "buy", "buyThreshold"); ok {
			th.Buy = v
		}
		if v, ok := floatFrom(custom, "sell", "sellThreshold"); ok {
			th.Sell = v
		}
		if v, ok := custom["max_risk"]; ok {
			th.MaxRisk = strings.ToLower(fmt.Sprint(v))
		}
	}
	total := score.Total
	confidence := int(math.Round(total))
	risk := strings.ToLower(score.RiskLevel)
	if risk == "" {
		risk = "low"
	}
	trend := strings.ToLower(score.TrendDirection)
	if trend == "" {
		trend = "sideways"
	}
	maxRank := riskRank[th.MaxRisk]
	if _, ok := riskRank[th.MaxRisk]; !ok {
		maxRank = 2
	}
	rr := riskRank[risk]

	if trend == "down" || total <= th.Sell || rr > maxRank {
		reasons := []string{}
		if trend == "down" {
			reasons = append(reasons, "趋势转弱")
		}
		if total <= th.Sell {
			reasons = append(reasons, fmt.Sprintf("综合分偏低(%v)", total))
		}
		if rr > maxRank {
			reasons = append(reasons, fmt.Sprintf("风险%s超出%s上限", risk, profile))
		}
		reason := strings.Join(reasons, "；")
		if reason == "" {
			reason = "规避风险"
		}
		return Decision{Signal: "SELL", Confidence: confidence, Reason: reason}
	}
	if total >= th.Buy && rr <= maxRank && trend != "down" {
		tagBits := score.Tags
		if len(tagBits) > 3 {
			tagBits = tagBits[:3]
		}
		return Decision{
			Signal:     "BUY",
			Confidence: confidence,
			Reason:     fmt.Sprintf("综合分%v达标；%s", total, strings.Join(tagBits, "、")),
		}
	}
	return Decision{
		Signal:     "HOLD",
		Confidence: confidence,
		Reason:     fmt.Sprintf("综合分%v，等待更强信号", total),
	}
}

func floatFrom(m map[string]any, keys ...string) (float64, bool) {
	for _, k := range keys {
		if v, ok := m[k]; ok && v != nil {
			switch x := v.(type) {
			case float64:
				return x, true
			case int:
				return float64(x), true
			}
		}
	}
	return 0, false
}

type Signal struct {
	OK         bool
	Symbol     string
	Market     string
	Price      *float64
	Signal     string
	Score      float64
	Confidence int
	Reason     string
	Metrics    Metrics
	ScoreDetail Score
}

func EvaluateSymbol(symbol, market, profile string, bars []Bar, cfg map[string]any) Signal {
	weights := MergeProfileConfig(profile, cfg)
	res := ComputeFromKlines(bars, profile, weights)
	if !res.OK {
		return Signal{
			OK: false, Symbol: symbol, Market: market,
			Signal: "HOLD", Reason: res.Reason,
		}
	}
	dec := DecideSignal(res.Score, profile, cfg)
	price := res.Metrics.Get("latestClose", 0)
	return Signal{
		OK: true, Symbol: symbol, Market: market, Price: &price,
		Signal: dec.Signal, Score: res.Score.Total, Confidence: dec.Confidence,
		Reason: dec.Reason, Metrics: res.Metrics, ScoreDetail: res.Score,
	}
}
