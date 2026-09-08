package factor

import (
	"fmt"
	"math"
)

// Bar is one daily OHLCV row (time ascending).
type Bar struct {
	Date   string
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

type Metrics struct {
	OK           bool
	Reason       string
	HistoryCount int
	TradeDate    string
	Values       map[string]float64
	Alpha101     map[string]float64
	Alpha158     map[string]float64
	Alpha101N    int
	Alpha158N    int
}

func (m Metrics) Get(key string, def float64) float64 {
	if m.Values == nil {
		return def
	}
	if v, ok := m.Values[key]; ok {
		return finite(v, def)
	}
	return def
}

func ComputeMetrics(bars []Bar) Metrics {
	n := len(bars)
	if n < 20 {
		return Metrics{OK: false, Reason: fmt.Sprintf("K线数据不足（%d<20），无法计算因子", n), HistoryCount: n}
	}
	close := make([]float64, n)
	high := make([]float64, n)
	low := make([]float64, n)
	open := make([]float64, n)
	volume := make([]float64, n)
	typical := make([]float64, n)
	for i, b := range bars {
		close[i] = b.Close
		high[i] = b.High
		low[i] = b.Low
		open[i] = b.Open
		volume[i] = b.Volume
		typical[i] = (b.High + b.Low + b.Close) / 3
	}

	latestClose := finite(close[n-1], 0)
	prevClose := latestClose
	if n > 1 {
		prevClose = finite(close[n-2], latestClose)
	}
	ma := func(length int) float64 {
		if n < length {
			return 0
		}
		return finite(rollingMean(close, length), 0)
	}
	ma5, ma10, ma20, ma30 := ma(5), ma(10), ma(20), ma(30)
	ma60, ma120 := ma(60), ma(120)
	ema12 := finite(ewmaLast(close, 12), 0)
	ema26 := finite(ewmaLast(close, 26), 0)

	bollMid := ma20
	bollStd := finite(rollingStd(close, 20), 0)
	bollUpper := bollMid + 2*bollStd
	bollLower := bollMid - 2*bollStd
	bollBW := ratio(bollUpper-bollLower, bollMid) * 100
	bollB := 50.0
	if bollUpper != bollLower {
		bollB = ratio(latestClose-bollLower, bollUpper-bollLower) * 100
	}

	high20 := finite(rollingMax(high, 20), 0)
	low20 := finite(rollingMin(low, 20), 0)
	high60, low60 := high20, low20
	if n >= 60 {
		high60 = finite(rollingMax(high, 60), 0)
		low60 = finite(rollingMin(low, 60), 0)
	}
	pp20 := 50.0
	if high20 != low20 {
		pp20 = ratio(latestClose-low20, high20-low20) * 100
	}
	pp60 := 50.0
	if high60 != low60 {
		pp60 = ratio(latestClose-low60, high60-low60) * 100
	}
	dh20 := ratio(latestClose-high20, high20) * 100
	dh60 := ratio(latestClose-high60, high60) * 100
	dl20 := ratio(latestClose-low20, low20) * 100

	avgVol5 := finite(rollingMean(volume, 5), 0)
	avgVol20 := finite(rollingMean(volume, 20), 0)
	avgVol60 := avgVol20
	if n >= 60 {
		avgVol60 = finite(rollingMean(volume, 60), 0)
	}
	latestVol := finite(volume[n-1], 0)
	vr5 := ratio(latestVol, avgVol5)
	vr20 := ratio(latestVol, avgVol20)
	vr60 := ratio(latestVol, avgVol60)
	volTrend20 := ratio(avgVol5-avgVol20, avgVol20) * 100

	dollar := make([]float64, n)
	for i := 0; i < n; i++ {
		dollar[i] = close[i] * volume[i]
	}
	avgDollar20 := finite(rollingMean(dollar, 20), 0)
	cvCorr := finite(corrTail(close, volume, 20), 0)

	tv := make([]float64, n)
	for i := 0; i < n; i++ {
		tv[i] = typical[i] * volume[i]
	}
	volSum20 := finite(0, 0)
	for i := n - 20; i < n; i++ {
		volSum20 += volume[i]
	}
	vwap20 := latestClose
	if volSum20 != 0 {
		s := 0.0
		for i := n - 20; i < n; i++ {
			s += tv[i]
		}
		vwap20 = ratio(s, volSum20)
	}
	vwapDist := 0.0
	if vwap20 != 0 {
		vwapDist = ratio(latestClose-vwap20, vwap20) * 100
	}

	latestOpen := finite(open[n-1], 0)
	kMid := ratio(latestClose-latestOpen, latestOpen) * 100
	upperShadow := ratio(finite(high[n-1], 0)-math.Max(latestOpen, latestClose), latestClose) * 100
	lowerShadow := ratio(math.Min(latestOpen, latestClose)-finite(low[n-1], 0), latestClose) * 100

	atr14 := atr(high, low, close, 14)
	atrPct := ratio(atr14, latestClose) * 100
	vol20 := volatility(close, 20)
	ret20 := periodReturn(close, 20)
	retVolRatio := ratio(ret20, vol20)

	ma25 := ma(25)
	maSlope := 0.0
	if n >= 25 && ma25 != 0 {
		maSlope = ratio(ma20-ma25, ma25) * 100
	}

	vals := map[string]float64{
		"latestClose":             roundN(latestClose, 4),
		"dayChangePercent":        roundN(ratio(latestClose-prevClose, prevClose)*100, 2),
		"ma5":                     roundN(ma5, 4),
		"ma10":                    roundN(ma10, 4),
		"ma20":                    roundN(ma20, 4),
		"ma30":                    roundN(ma30, 4),
		"ma60":                    roundN(ma60, 4),
		"ma120":                   roundN(ma120, 4),
		"ema12":                   roundN(ema12, 4),
		"ema26":                   roundN(ema26, 4),
		"return5":                 roundN(periodReturn(close, 5), 2),
		"return20":                roundN(ret20, 2),
		"return60":                roundN(periodReturn(close, 60), 2),
		"returnVolatilityRatio20": roundN(retVolRatio, 2),
		"maSlope20":               roundN(maSlope, 2),
		"maSpread20_60":           roundN(ratio(ma20-ma60, ma60)*100, 2),
		"adx14":                   roundN(adx(high, low, close, 14), 2),
		"macdHist":                roundN(macdHist(close), 4),
		"kMid":                    roundN(kMid, 2),
		"upperShadow":             roundN(upperShadow, 2),
		"lowerShadow":             roundN(lowerShadow, 2),
		"pricePosition20":         roundN(pp20, 2),
		"pricePosition60":         roundN(pp60, 2),
		"bollMid20":               roundN(bollMid, 4),
		"bollUpper20":             roundN(bollUpper, 4),
		"bollLower20":             roundN(bollLower, 4),
		"bollBandwidth20":         roundN(bollBW, 2),
		"bollPercentB20":          roundN(bollB, 2),
		"vwap20":                  roundN(vwap20, 4),
		"vwapDistance20":          roundN(vwapDist, 2),
		"rsi6":                    roundN(rsiSMA(close, 6), 2),
		"rsi14":                   roundN(rsiSMA(close, 14), 2),
		"rsi28":                   roundN(rsiSMA(close, 28), 2),
		"roc12":                   roundN(periodReturn(close, 12), 2),
		"stochK14":                roundN(stochK(high, low, close, 14), 2),
		"williamsR14":             roundN(williamsR(high, low, close, 14), 2),
		"cci20":                   roundN(cci(high, low, close, 20), 2),
		"distanceHigh20":          roundN(dh20, 2),
		"distanceHigh60":          roundN(dh60, 2),
		"distanceLow20":           roundN(dl20, 2),
		"supportDistance":         roundN(math.Abs(dl20), 2),
		"avgVolume5":              roundN(avgVol5, 2),
		"avgVolume20":             roundN(avgVol20, 2),
		"avgVolume60":             roundN(avgVol60, 2),
		"volumeRatio5":            roundN(vr5, 2),
		"volumeRatio20":           roundN(vr20, 2),
		"volumeRatio60":           roundN(vr60, 2),
		"volumeTrend20":           roundN(volTrend20, 2),
		"avgDollarVolume20":       roundN(avgDollar20, 2),
		"obvSlope20":              roundN(obvSlope(close, volume, 20), 2),
		"mfi14":                   roundN(mfi(high, low, close, volume, 14), 2),
		"cmf20":                   roundN(cmf(high, low, close, volume, 20), 4),
		"closeVolumeCorr20":       roundN(cvCorr, 4),
		"volatility5":             roundN(volatility(close, 5), 2),
		"volatility20":            roundN(vol20, 2),
		"volatility60":            roundN(volatility(close, 60), 2),
		"atr14":                   roundN(atr14, 4),
		"atr14Percent":            roundN(atrPct, 2),
		"downsideVol20":           roundN(downsideVol(close, 20), 2),
		"maxDrawdown20":           roundN(maxDrawdown(close, 20), 2),
		"maxDrawdown60":           roundN(maxDrawdown(close, 60), 2),
	}

	a101, a158 := computeAlphas(bars)
	tradeDate := bars[n-1].Date
	return Metrics{
		OK:           true,
		HistoryCount: n,
		TradeDate:    tradeDate,
		Values:       vals,
		Alpha101:     a101,
		Alpha158:     a158,
		Alpha101N:    len(a101),
		Alpha158N:    len(a158),
	}
}

func atr(high, low, close []float64, length int) float64 {
	n := len(close)
	if n < 2 {
		return 0
	}
	tr := make([]float64, n)
	tr[0] = high[0] - low[0]
	for i := 1; i < n; i++ {
		hl := high[i] - low[i]
		hc := math.Abs(high[i] - close[i-1])
		lc := math.Abs(low[i] - close[i-1])
		tr[i] = math.Max(hl, math.Max(hc, lc))
	}
	return finite(rollingMean(tr, length), 0)
}

func adx(high, low, close []float64, length int) float64 {
	n := len(close)
	if n < length*2 {
		return 0
	}
	plusDM := make([]float64, n)
	minusDM := make([]float64, n)
	tr := make([]float64, n)
	for i := 1; i < n; i++ {
		up := high[i] - high[i-1]
		down := low[i-1] - low[i]
		if up > down && up > 0 {
			plusDM[i] = up
		}
		if down > up && down > 0 {
			minusDM[i] = down
		}
		hl := high[i] - low[i]
		hc := math.Abs(high[i] - close[i-1])
		lc := math.Abs(low[i] - close[i-1])
		tr[i] = math.Max(hl, math.Max(hc, lc))
	}
	smooth := func(xs []float64) []float64 {
		out := make([]float64, n)
		sum := 0.0
		for i := 1; i <= length && i < n; i++ {
			sum += xs[i]
		}
		if length < n {
			out[length] = sum
		}
		for i := length + 1; i < n; i++ {
			out[i] = out[i-1] - out[i-1]/float64(length) + xs[i]
		}
		return out
	}
	trS := smooth(tr)
	pS := smooth(plusDM)
	mS := smooth(minusDM)
	dx := make([]float64, n)
	for i := length; i < n; i++ {
		if trS[i] == 0 {
			continue
		}
		pDI := 100 * pS[i] / trS[i]
		mDI := 100 * mS[i] / trS[i]
		den := pDI + mDI
		if den == 0 {
			continue
		}
		dx[i] = 100 * math.Abs(pDI-mDI) / den
	}
	return finite(rollingMean(dx, length), 0)
}

func macdHist(close []float64) float64 {
	ema12 := ewmaSeries(close, 12)
	ema26 := ewmaSeries(close, 26)
	dif := make([]float64, len(close))
	for i := range close {
		dif[i] = ema12[i] - ema26[i]
	}
	dea := ewmaSeries(dif, 9)
	return finite(last(dif)-last(dea), 0)
}

func ewmaSeries(xs []float64, span int) []float64 {
	out := make([]float64, len(xs))
	if len(xs) == 0 || span <= 0 {
		return out
	}
	alpha := 2.0 / (float64(span) + 1)
	out[0] = xs[0]
	for i := 1; i < len(xs); i++ {
		out[i] = alpha*xs[i] + (1-alpha)*out[i-1]
	}
	return out
}

func stochK(high, low, close []float64, length int) float64 {
	lo := rollingMin(low, length)
	hi := rollingMax(high, length)
	return finite(ratio(last(close)-lo, hi-lo)*100, 50)
}

func williamsR(high, low, close []float64, length int) float64 {
	lo := rollingMin(low, length)
	hi := rollingMax(high, length)
	return finite(ratio(hi-last(close), hi-lo)*-100, -50)
}

func cci(high, low, close []float64, length int) float64 {
	n := len(close)
	if n < length {
		return 0
	}
	tp := make([]float64, n)
	for i := 0; i < n; i++ {
		tp[i] = (high[i] + low[i] + close[i]) / 3
	}
	sma := rollingMean(tp, length)
	win := tp[n-length:]
	mad := 0.0
	for _, v := range win {
		mad += math.Abs(v - sma)
	}
	mad /= float64(length)
	return finite(ratio(tp[n-1]-sma, 0.015*mad), 0)
}

func obvSlope(close, volume []float64, length int) float64 {
	n := len(close)
	if n <= length {
		return 0
	}
	obv := make([]float64, n)
	for i := 1; i < n; i++ {
		obv[i] = obv[i-1] + sign(close[i]-close[i-1])*volume[i]
	}
	recent := finite(obv[n-1], 0)
	past := finite(obv[n-length], 0)
	base := math.Abs(past)
	if base == 0 {
		base = math.Abs(recent)
		if base == 0 {
			base = 1
		}
	}
	return ratio(recent-past, base) * 100
}

func mfi(high, low, close, volume []float64, length int) float64 {
	n := len(close)
	if n < length+1 {
		return 50
	}
	var pos, neg float64
	for i := n - length; i < n; i++ {
		tp := (high[i] + low[i] + close[i]) / 3
		prev := (high[i-1] + low[i-1] + close[i-1]) / 3
		mf := tp * volume[i]
		if tp > prev {
			pos += mf
		} else if tp < prev {
			neg += mf
		}
	}
	if neg == 0 {
		return 100
	}
	r := ratio(pos, neg)
	return 100 - 100/(1+r)
}

func cmf(high, low, close, volume []float64, length int) float64 {
	n := len(close)
	if n < length {
		return 0
	}
	var mfv, vol float64
	for i := n - length; i < n; i++ {
		hl := high[i] - low[i]
		mfm := 0.0
		if hl != 0 {
			mfm = ((close[i] - low[i]) - (high[i] - close[i])) / hl
		}
		mfv += mfm * volume[i]
		vol += volume[i]
	}
	return finite(ratio(mfv, vol), 0)
}
