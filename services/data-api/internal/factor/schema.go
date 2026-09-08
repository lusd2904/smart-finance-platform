package factor

// Static factor schema matching Python factor_service.py + alpha_engine.alpha_schema().
func GetSchema() map[string]interface{} {
	families := []map[string]interface{}{
		{
			"key": "trend", "label": "趋势因子",
			"inputs": []string{"ma5", "ma10", "ma20", "ma30", "ma60", "ma120", "ema12", "ema26",
				"return20", "return60", "maSlope20", "maSpread20_60", "adx14", "macdHist"},
			"desc": "均线多空排列、动量斜率、ADX/MACD 趋势确认",
		},
		{
			"key": "priceAction", "label": "价型因子",
			"inputs": []string{"kMid", "upperShadow", "lowerShadow", "pricePosition20", "pricePosition60",
				"bollPercentB20", "vwapDistance20"},
			"desc": "K线实体/影线形态、区间位置、布林%B、VWAP 偏离",
		},
		{
			"key": "momentum", "label": "动量因子",
			"inputs": []string{"rsi6", "rsi14", "rsi28", "roc12", "stochK14", "williamsR14", "cci20"},
			"desc": "RSI/ROC/KDJ/威廉/CCI 等动量指标",
		},
		{
			"key": "breakout", "label": "突破因子",
			"inputs": []string{"distanceHigh20", "distanceHigh60", "volumeRatio20", "volumeRatio60",
				"dayChangePercent", "bollBandwidth20"},
			"desc": "距区间高点距离、放量突破、布林收口",
		},
		{
			"key": "volumeFlow", "label": "量能资金因子",
			"inputs": []string{"volumeRatio5", "volumeRatio20", "obvSlope20", "mfi14", "cmf20", "closeVolumeCorr20"},
			"desc": "OBV/MFI/CMF 资金流向、量价相关性",
		},
		{
			"key": "reversion", "label": "回归因子",
			"inputs": []string{"rsi14", "stochK14", "bollPercentB20", "supportDistance", "distanceLow20", "return20"},
			"desc": "超卖回升、支撑反弹、布林下轨回归",
		},
		{
			"key": "volatility", "label": "波动因子",
			"inputs": []string{"volatility5", "volatility20", "volatility60", "atr14Percent",
				"bollBandwidth20", "downsideVol20"},
			"desc": "收益波动率、ATR%、下行波动",
		},
		{
			"key": "liquidity", "label": "流动性因子",
			"inputs": []string{"avgVolume20", "avgDollarVolume20", "volumeTrend20", "vwapDistance20"},
			"desc": "成交量/成交额、量能趋势、VWAP 偏离",
		},
		{
			"key": "alpha101", "label": "WorldQuant Alpha101",
			"desc": "经典 Alpha101 时序实现（截面 rank 退化为滚动分位），覆盖动量、量价相关、日内形态等",
			"inputs": []string{"alpha001", "alpha006", "alpha012", "alpha018", "alpha023",
				"alpha041", "alpha054", "alpha101"},
		},
		{
			"key": "alpha158", "label": "Qlib Alpha158",
			"desc": "K 线形态 + OPEN/HIGH/LOW/VWAP/VOLUME 相对收盘 + 5/10/20/30/60 滚动算子（ROC/MA/STD/BETA/CORR/RSV 等）",
			"inputs": []string{"KMID", "KLEN", "ROC5", "MA20", "STD20", "CORR20", "RSV20", "SUMD20"},
		},
		{
			"key": "alpha101Cs", "label": "Alpha101 截面 rank",
			"desc": "对当日全市场因子值做百分位 rank，还原原文截面 rank() 口径",
			"inputs": []string{"csMom20", "csVolRatio20", "csRsi14", "csBreakout",
				"csAlpha001", "csAlpha006", "csAlpha012", "csAlpha023", "csAlpha041", "csAlpha101"},
		},
	}
	return map[string]interface{}{
		"version":      "quant-factor-v2",
		"familyCount":  len(families),
		"profiles":     []string{"conservative", "balanced", "aggressive"},
		"families":     families,
		"alphaEngine":  "alpha-101-158-v1",
	}
}
