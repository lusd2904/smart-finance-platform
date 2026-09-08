package factor

const SchemaVersion = "quant-factor-v2"

var profileWeights = map[string]map[string]float64{
	"conservative": {
		"trend": 0.24, "priceAction": 0.14, "momentum": 0.10, "breakout": 0.06,
		"volumeFlow": 0.10, "reversion": 0.20, "volatility": 0.16, "liquidity": 0.10,
	},
	"balanced": {
		"trend": 0.30, "priceAction": 0.14, "momentum": 0.18, "breakout": 0.16,
		"volumeFlow": 0.12, "reversion": 0.08, "volatility": 0.10, "liquidity": 0.06,
	},
	"aggressive": {
		"trend": 0.34, "priceAction": 0.12, "momentum": 0.26, "breakout": 0.28,
		"volumeFlow": 0.16, "reversion": 0.02, "volatility": 0.06, "liquidity": 0.05,
	},
}

var profileRiskMult = map[string]float64{
	"conservative": 1.4, "balanced": 1.0, "aggressive": 0.7,
}

var weightAliases = map[string]string{
	"volume": "volumeFlow", "volume_flow": "volumeFlow",
	"price_action": "priceAction", "priceaction": "priceAction",
	"value": "reversion", "quality": "liquidity",
}

type Score struct {
	FactorVersion   string   `json:"factorVersion"`
	StrategyProfile string   `json:"strategyProfile"`
	Total           float64  `json:"total"`
	Trend           float64  `json:"trend"`
	PriceAction     float64  `json:"priceAction"`
	Momentum        float64  `json:"momentum"`
	Breakout        float64  `json:"breakout"`
	VolumeFlow      float64  `json:"volumeFlow"`
	Reversion       float64  `json:"reversion"`
	Volatility      float64  `json:"volatility"`
	Liquidity       float64  `json:"liquidity"`
	RiskPenalty     float64  `json:"riskPenalty"`
	RiskLevel       string   `json:"riskLevel"`
	TrendDirection  string   `json:"trendDirection"`
	Tags            []string `json:"tags"`
}

func NormalizeProfile(profile string) string {
	switch profile {
	case "conservative", "balanced", "aggressive":
		return profile
	default:
		return "balanced"
	}
}

func MergeWeights(profile string, custom map[string]float64) map[string]float64 {
	key := NormalizeProfile(profile)
	out := map[string]float64{}
	for k, v := range profileWeights[key] {
		out[k] = v
	}
	if custom == nil {
		return out
	}
	for name, value := range custom {
		mapped := name
		if a, ok := weightAliases[name]; ok {
			mapped = a
		}
		if _, ok := out[mapped]; !ok {
			continue
		}
		out[mapped] = value
	}
	return out
}

// MergeProfileConfig accepts the plat_strategy_profile JSON shape
// ({weights:{...}, buyThreshold, sellThreshold, max_risk}).
func MergeProfileConfig(profile string, cfg map[string]any) map[string]float64 {
	key := NormalizeProfile(profile)
	out := map[string]float64{}
	for k, v := range profileWeights[key] {
		out[k] = v
	}
	if cfg == nil {
		return out
	}
	raw := cfg
	if nested, ok := cfg["weights"].(map[string]any); ok {
		raw = nested
	}
	for name, value := range raw {
		mapped := name
		if a, ok := weightAliases[name]; ok {
			mapped = a
		}
		if _, exists := out[mapped]; !exists {
			continue
		}
		switch x := value.(type) {
		case float64:
			out[mapped] = x
		case int:
			out[mapped] = float64(x)
		}
	}
	return out
}

func ScoreMetrics(m Metrics, profile string, weights map[string]float64) Score {
	profile = NormalizeProfile(profile)
	g := func(k string, d float64) float64 { return m.Get(k, d) }

	latestClose := g("latestClose", 0)
	ma5, ma10, ma20 := g("ma5", 0), g("ma10", 0), g("ma20", 0)
	ma30, ma60, ma120 := g("ma30", 0), g("ma60", 0), g("ma120", 0)
	ema12, ema26 := g("ema12", 0), g("ema26", 0)
	rsi6, rsi14, rsi28 := g("rsi6", 50), g("rsi14", 50), g("rsi28", 50)
	tags := []string{}

	trend := 0.0
	if latestClose != 0 && ma20 != 0 && latestClose >= ma20 {
		trend += 11
		tags = append(tags, "站上20日线")
	}
	if ma5 != 0 && ma10 != 0 && ma5 >= ma10 {
		trend += 4
	}
	if ma20 != 0 && ma60 != 0 && ma20 >= ma60 {
		trend += 10
		tags = append(tags, "20/60多头")
	}
	if ma60 != 0 && ma120 != 0 && ma60 >= ma120 {
		trend += 6
		tags = append(tags, "中期趋势顺")
	}
	if ma20 != 0 && ma30 != 0 && ma20 >= ma30 {
		trend += 3
	}
	if ema12 != 0 && ema26 != 0 && ema12 >= ema26 {
		trend += 5
	}
	trend += clamp(g("return20", 0)/1.8, -8, 10)
	trend += clamp(g("return60", 0)/3.5, -6, 8)
	trend += clamp(g("maSlope20", 0)/1.8, -5, 6)
	trend += clamp(g("maSpread20_60", 0)/2.2, -4, 6)
	if g("adx14", 0) >= 25 {
		trend += 5
		tags = append(tags, "ADX趋势确认")
	}
	if g("macdHist", 0) > 0 {
		trend += 4
		tags = append(tags, "MACD偏多")
	}

	priceAction := 0.0
	pp20, pp60 := g("pricePosition20", 50), g("pricePosition60", 50)
	kMid := g("kMid", 0)
	if pp20 >= 55 && pp20 <= 92 {
		priceAction += 7
	} else if pp20 >= 92 {
		priceAction += 3
	} else if pp20 <= 18 {
		priceAction -= 5
	}
	if pp60 >= 50 && pp60 <= 90 {
		priceAction += 5
	}
	if kMid > 0 {
		priceAction += clamp(kMid*1.2, 0, 5)
	}
	if g("lowerShadow", 0) >= g("upperShadow", 0)*1.4 && kMid >= -1 {
		priceAction += 4
		tags = append(tags, "下影承接")
	}
	if g("upperShadow", 0) >= 3 && kMid < 0 {
		priceAction -= 5
	}
	bollB := g("bollPercentB20", 50)
	if bollB >= 45 && bollB <= 88 {
		priceAction += 4
	} else if bollB > 115 {
		priceAction -= 4
	}
	priceAction += clamp(g("vwapDistance20", 0)/2.5, -4, 4)

	momentum := 0.0
	momentum += clamp(g("roc12", 0)/2.0, -7, 8)
	momentum += clamp(g("returnVolatilityRatio20", 0)*2.0, -6, 8)
	if rsi14 >= 52 && rsi14 <= 72 {
		momentum += 7
		tags = append(tags, "RSI强势区")
	} else if rsi14 > 78 {
		momentum -= 6
	} else if rsi14 < 35 {
		momentum -= 4
	}
	if rsi6 >= rsi14 && rsi14 >= rsi28 && rsi14 >= 50 {
		momentum += 5
	}
	stoch := g("stochK14", 50)
	if stoch >= 45 && stoch <= 82 {
		momentum += 4
	} else if stoch > 92 {
		momentum -= 4
	}
	wr := g("williamsR14", -50)
	if wr >= -65 && wr <= -20 {
		momentum += 3
	} else if wr > -10 {
		momentum -= 3
	}
	cciV := g("cci20", 0)
	if cciV >= 0 && cciV <= 180 {
		momentum += 4
	} else if cciV > 240 || cciV < -180 {
		momentum -= 4
	}

	breakout := 0.0
	dh20, dh60 := g("distanceHigh20", 0), g("distanceHigh60", 0)
	vr20 := g("volumeRatio20", 0)
	if dh20 >= 0 {
		breakout += 11
		tags = append(tags, "20日突破")
	} else if dh20 >= -2 {
		breakout += 7
		tags = append(tags, "接近20日高点")
	}
	if dh60 >= 0 {
		breakout += 8
		tags = append(tags, "60日突破")
	} else if dh60 >= -3.5 {
		breakout += 4
	}
	if vr20 >= 1.5 {
		breakout += 7
		tags = append(tags, "明显放量")
	} else if vr20 >= 1.15 {
		breakout += 4
		tags = append(tags, "温和放量")
	}
	if g("volumeRatio60", 0) >= 1.2 {
		breakout += 3
	}
	if g("return20", 0) > 0 && g("dayChangePercent", 0) > 0 {
		breakout += 4
	}
	if g("bollBandwidth20", 0) <= 8 && dh20 >= -4 {
		breakout += 3
	}

	volumeFlow := 0.0
	if g("volumeRatio5", 0) >= 1.1 && g("dayChangePercent", 0) > 0 {
		volumeFlow += 5
	}
	if g("obvSlope20", 0) > 0 {
		volumeFlow += clamp(g("obvSlope20", 0)/4, 0, 7)
		tags = append(tags, "OBV走强")
	}
	mfiV := g("mfi14", 50)
	if mfiV >= 45 && mfiV <= 75 {
		volumeFlow += 5
	} else if mfiV > 85 {
		volumeFlow -= 4
	} else if mfiV < 25 {
		volumeFlow -= 3
	}
	cmfV := g("cmf20", 0)
	if cmfV > 0.05 {
		volumeFlow += 5
		tags = append(tags, "资金流入")
	} else if cmfV < -0.08 {
		volumeFlow -= 5
	}
	volumeFlow += clamp(g("closeVolumeCorr20", 0)*5, -4, 4)

	reversion := 0.0
	support := g("supportDistance", 100)
	if rsi14 >= 28 && rsi14 <= 45 && support <= 4 {
		reversion += 10
		tags = append(tags, "支撑回升")
	}
	if rsi14 < 35 && g("dayChangePercent", 0) > 0 {
		reversion += 7
		tags = append(tags, "RSI低位反弹")
	}
	if latestClose != 0 && ma20 != 0 && latestClose < ma20 && g("return20", 0) > -8 {
		reversion += 4
	}
	if g("bollPercentB20", 50) <= 18 && g("dayChangePercent", 0) > 0 {
		reversion += 6
		tags = append(tags, "布林下轨反弹")
	}
	if g("distanceLow20", 0) <= 4 && g("return5", 0) > 0 {
		reversion += 4
	}

	volatility := 0.0
	vol20 := g("volatility20", 0)
	atrPct := g("atr14Percent", 0)
	bandwidth := g("bollBandwidth20", 0)
	if vol20 >= 0.8 && vol20 <= 3.4 {
		volatility += 7
	} else if vol20 < 0.8 && g("return20", 0) > 0 {
		volatility += 2
	} else if vol20 >= 5.2 {
		volatility -= 8
	}
	if atrPct >= 0.4 && atrPct <= 4 {
		volatility += 5
	} else if atrPct > 6 {
		volatility -= 7
	}
	if bandwidth >= 4 && bandwidth <= 18 {
		volatility += 4
	} else if bandwidth > 30 {
		volatility -= 4
	}
	volatility -= clamp((g("downsideVol20", 0)-2.5)*1.5, 0, 6)

	liquidity := 0.0
	adv20 := g("avgDollarVolume20", 0)
	av20 := g("avgVolume20", 0)
	if adv20 >= 50_000_000 {
		liquidity += 8
	} else if adv20 >= 5_000_000 {
		liquidity += 5
	} else if av20 > 0 {
		liquidity += 2
	}
	if g("volumeTrend20", 0) > 0 {
		liquidity += clamp(g("volumeTrend20", 0)/12, 0, 4)
	}
	if abs(g("vwapDistance20", 0)) <= 5 {
		liquidity += 3
	}

	riskPenalty := 0.0
	riskLevel := "low"
	if vol20 >= 5.2 || atrPct >= 6 {
		riskPenalty += 14
		riskLevel = "high"
	} else if vol20 >= 3.4 || atrPct >= 4 {
		riskPenalty += 6
		riskLevel = "medium"
	}
	if rsi14 >= 82 {
		riskPenalty += 9
		if riskLevel == "low" {
			riskLevel = "medium"
		}
	}
	if g("return20", 0) <= -12 || dh20 <= -18 {
		riskPenalty += 12
		riskLevel = "high"
	}
	if g("maxDrawdown20", 0) <= -14 || g("maxDrawdown60", 0) <= -22 {
		riskPenalty += 9
		riskLevel = "high"
	}
	if g("downsideVol20", 0) >= 4.5 {
		riskPenalty += 6
		if riskLevel == "low" {
			riskLevel = "medium"
		}
	}
	riskPenalty *= profileRiskMult[profile]

	if weights == nil {
		weights = MergeWeights(profile, nil)
	}
	rawTotal := 42 +
		trend*weights["trend"] +
		priceAction*weights["priceAction"] +
		momentum*weights["momentum"] +
		breakout*weights["breakout"] +
		volumeFlow*weights["volumeFlow"] +
		reversion*weights["reversion"] +
		volatility*weights["volatility"] +
		liquidity*weights["liquidity"] -
		riskPenalty
	total := roundN(clamp(rawTotal, 0, 100), 2)
	dir := "sideways"
	if trend+momentum*0.35 >= 22 {
		dir = "up"
	} else if trend <= -5 {
		dir = "down"
	}
	if len(tags) == 0 {
		tags = []string{"持续观察"}
	}
	return Score{
		FactorVersion:   SchemaVersion,
		StrategyProfile: profile,
		Total:           total,
		Trend:           roundN(trend, 2),
		PriceAction:     roundN(priceAction, 2),
		Momentum:        roundN(momentum, 2),
		Breakout:        roundN(breakout, 2),
		VolumeFlow:      roundN(volumeFlow, 2),
		Reversion:       roundN(reversion, 2),
		Volatility:      roundN(volatility, 2),
		Liquidity:       roundN(liquidity, 2),
		RiskPenalty:     roundN(riskPenalty, 2),
		RiskLevel:       riskLevel,
		TrendDirection:  dir,
		Tags:            tags,
	}
}

func abs(v float64) float64 {
	if v < 0 {
		return -v
	}
	return v
}

type Result struct {
	OK      bool
	Reason  string
	Metrics Metrics
	Score   Score
}

func ComputeFromKlines(bars []Bar, profile string, weights map[string]float64) Result {
	m := ComputeMetrics(bars)
	if !m.OK {
		return Result{OK: false, Reason: m.Reason, Metrics: m}
	}
	return Result{OK: true, Metrics: m, Score: ScoreMetrics(m, profile, weights)}
}
