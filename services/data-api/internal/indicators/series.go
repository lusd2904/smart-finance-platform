package indicators

import "math"

type Bar struct {
	Date   string
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

// Calculate returns indicator time series matching Python IndicatorService.calculate.
func Calculate(bars []Bar) map[string]interface{} {
	n := len(bars)
	if n == 0 {
		return map[string]interface{}{
			"symbol": "", "market": "", "dates": []string{},
			"ma": map[string][]interface{}{}, "ema": map[string][]interface{}{},
			"macd": map[string][]interface{}{}, "rsi": map[string][]interface{}{},
			"kdj": map[string][]interface{}{}, "boll": map[string][]interface{}{},
			"atr": []interface{}{}, "cci": []interface{}{}, "wr": []interface{}{},
			"obv": []interface{}{}, "volMa": map[string][]interface{}{},
		}
	}
	dates := make([]string, n)
	close := make([]float64, n)
	high := make([]float64, n)
	low := make([]float64, n)
	vol := make([]float64, n)
	for i, b := range bars {
		dates[i] = b.Date
		close[i] = b.Close
		high[i] = b.High
		low[i] = b.Low
		vol[i] = b.Volume
	}
	ma5 := rollingMean(close, 5)
	ma10 := rollingMean(close, 10)
	ma20 := rollingMean(close, 20)
	ma30 := rollingMean(close, 30)
	ma60 := rollingMean(close, 60)
	ema12 := emaSeries(close, 12)
	ema26 := emaSeries(close, 26)
	macdLine, signal, hist := macd(close)
	rsi6 := rsi(close, 6)
	rsi12 := rsi(close, 12)
	rsi24 := rsi(close, 24)
	k, d, j := kdj(high, low, close, 9, 3)
	bollMid, bollUp, bollLow := boll(close, 20, 2)
	atr14 := atr(high, low, close, 14)
	cci14 := cci(high, low, close, 14)
	wr14 := willr(high, low, close, 14)
	obv := obvSeries(close, vol)
	volMa5 := rollingMean(vol, 5)
	volMa10 := rollingMean(vol, 10)
	return map[string]interface{}{
		"dates": dates,
		"ma": map[string][]interface{}{
			"ma5": toNullable(ma5), "ma10": toNullable(ma10), "ma20": toNullable(ma20),
			"ma30": toNullable(ma30), "ma60": toNullable(ma60),
		},
		"ema": map[string][]interface{}{"ema12": toNullable(ema12), "ema26": toNullable(ema26)},
		"macd": map[string][]interface{}{"macd": toNullable(macdLine), "signal": toNullable(signal), "hist": toNullable(hist)},
		"rsi":  map[string][]interface{}{"rsi6": toNullable(rsi6), "rsi12": toNullable(rsi12), "rsi24": toNullable(rsi24)},
		"kdj":  map[string][]interface{}{"k": toNullable(k), "d": toNullable(d), "j": toNullable(j)},
		"boll": map[string][]interface{}{"mid": toNullable(bollMid), "upper": toNullable(bollUp), "lower": toNullable(bollLow)},
		"atr":  toNullable(atr14), "cci": toNullable(cci14), "wr": toNullable(wr14),
		"obv": toNullable(obv),
		"volMa": map[string][]interface{}{"volMa5": toNullable(volMa5), "volMa10": toNullable(volMa10)},
	}
}

func toNullable(xs []float64) []interface{} {
	out := make([]interface{}, len(xs))
	for i, v := range xs {
		if math.IsNaN(v) || math.IsInf(v, 0) {
			out[i] = nil
		} else {
			out[i] = v
		}
	}
	return out
}

func rollingMean(values []float64, length int) []float64 {
	n := len(values)
	out := make([]float64, n)
	for i := 0; i < n; i++ {
		if i+1 < length {
			out[i] = math.NaN()
			continue
		}
		sum := 0.0
		for j := i - length + 1; j <= i; j++ {
			sum += values[j]
		}
		out[i] = sum / float64(length)
	}
	return out
}

func emaSeries(values []float64, length int) []float64 {
	n := len(values)
	out := make([]float64, n)
	if n == 0 || length <= 0 {
		return out
	}
	k := 2.0 / (float64(length) + 1)
	out[0] = values[0]
	for i := 1; i < n; i++ {
		out[i] = values[i]*k + out[i-1]*(1-k)
	}
	return out
}

func macd(close []float64) ([]float64, []float64, []float64) {
	n := len(close)
	macdLine := make([]float64, n)
	signal := make([]float64, n)
	hist := make([]float64, n)
	if n < 26 {
		for i := range close {
			macdLine[i], signal[i], hist[i] = math.NaN(), math.NaN(), math.NaN()
		}
		return macdLine, signal, hist
	}
	e12 := emaSeries(close, 12)
	e26 := emaSeries(close, 26)
	for i := 0; i < n; i++ {
		if i < 25 {
			macdLine[i] = math.NaN()
		} else {
			macdLine[i] = e12[i] - e26[i]
		}
	}
	for i := 0; i < n; i++ {
		if math.IsNaN(macdLine[i]) {
			signal[i] = math.NaN()
			continue
		}
		if i == 25 {
			signal[i] = macdLine[i]
		} else if i > 25 {
			signal[i] = macdLine[i]*0.2 + signal[i-1]*0.8
		}
	}
	for i := 0; i < n; i++ {
		if math.IsNaN(macdLine[i]) || math.IsNaN(signal[i]) {
			hist[i] = math.NaN()
		} else {
			hist[i] = macdLine[i] - signal[i]
		}
	}
	return macdLine, signal, hist
}

func rsi(close []float64, length int) []float64 {
	n := len(close)
	out := make([]float64, n)
	if n < length+1 {
		for i := range out {
			out[i] = math.NaN()
		}
		return out
	}
	var avgGain, avgLoss float64
	for i := 1; i <= length; i++ {
		delta := close[i] - close[i-1]
		if delta > 0 {
			avgGain += delta
		} else {
			avgLoss -= delta
		}
	}
	avgGain /= float64(length)
	avgLoss /= float64(length)
	out[length] = calcRSI(avgGain, avgLoss)
	for i := length + 1; i < n; i++ {
		delta := close[i] - close[i-1]
		gain, loss := 0.0, 0.0
		if delta > 0 {
			gain = delta
		} else {
			loss = -delta
		}
		avgGain = (avgGain*float64(length-1) + gain) / float64(length)
		avgLoss = (avgLoss*float64(length-1) + loss) / float64(length)
		out[i] = calcRSI(avgGain, avgLoss)
	}
	for i := 0; i < length; i++ {
		out[i] = math.NaN()
	}
	return out
}

func calcRSI(avgGain, avgLoss float64) float64 {
	if avgLoss == 0 {
		if avgGain == 0 {
			return 50
		}
		return 100
	}
	rs := avgGain / avgLoss
	return 100 - (100 / (1 + rs))
}

func kdj(high, low, close []float64, length, signal int) ([]float64, []float64, []float64) {
	n := len(close)
	k := make([]float64, n)
	d := make([]float64, n)
	j := make([]float64, n)
	for i := 0; i < n; i++ {
		k[i], d[i], j[i] = math.NaN(), math.NaN(), math.NaN()
	}
	for i := length - 1; i < n; i++ {
		lo := rollingMinAt(low, i, length)
		hi := rollingMaxAt(high, i, length)
		rsv := 50.0
		if hi != lo {
			rsv = (close[i] - lo) / (hi - lo) * 100
		}
		if i == length-1 {
			k[i] = rsv
			d[i] = rsv
		} else {
			k[i] = rsv*0.333 + k[i-1]*0.667
			d[i] = k[i]*0.333 + d[i-1]*0.667
		}
		j[i] = 3*k[i] - 2*d[i]
	}
	return k, d, j
}

func boll(close []float64, length int, mult float64) ([]float64, []float64, []float64) {
	n := len(close)
	mid := rollingMean(close, length)
	up := make([]float64, n)
	low := make([]float64, n)
	for i := 0; i < n; i++ {
		if i+1 < length {
			up[i], low[i] = math.NaN(), math.NaN()
			continue
		}
		std := rollingStdAt(close, i, length)
		up[i] = mid[i] + mult*std
		low[i] = mid[i] - mult*std
	}
	return mid, up, low
}

func atr(high, low, close []float64, length int) []float64 {
	n := len(close)
	tr := make([]float64, n)
	for i := 0; i < n; i++ {
		if i == 0 {
			tr[i] = high[i] - low[i]
		} else {
			tr[i] = math.Max(high[i]-low[i], math.Max(math.Abs(high[i]-close[i-1]), math.Abs(low[i]-close[i-1])))
		}
	}
	return emaWilder(tr, length)
}

func cci(high, low, close []float64, length int) []float64 {
	n := len(close)
	out := make([]float64, n)
	tp := make([]float64, n)
	for i := 0; i < n; i++ {
		tp[i] = (high[i] + low[i] + close[i]) / 3
	}
	for i := 0; i < n; i++ {
		if i+1 < length {
			out[i] = math.NaN()
			continue
		}
		ma := rollingMeanAt(tp, i, length)
		md := 0.0
		for j := i - length + 1; j <= i; j++ {
			md += math.Abs(tp[j] - ma)
		}
		md /= float64(length)
		if md == 0 {
			out[i] = math.NaN()
		} else {
			out[i] = (tp[i] - ma) / (0.015 * md)
		}
	}
	return out
}

func willr(high, low, close []float64, length int) []float64 {
	n := len(close)
	out := make([]float64, n)
	for i := 0; i < n; i++ {
		if i+1 < length {
			out[i] = math.NaN()
			continue
		}
		hi := rollingMaxAt(high, i, length)
		lo := rollingMinAt(low, i, length)
		if hi == lo {
			out[i] = math.NaN()
		} else {
			out[i] = -100 * (hi - close[i]) / (hi - lo)
		}
	}
	return out
}

func obvSeries(close, vol []float64) []float64 {
	n := len(close)
	out := make([]float64, n)
	if n == 0 {
		return out
	}
	out[0] = vol[0]
	for i := 1; i < n; i++ {
		dir := 0.0
		if close[i] > close[i-1] {
			dir = 1
		} else if close[i] < close[i-1] {
			dir = -1
		}
		out[i] = out[i-1] + dir*vol[i]
	}
	return out
}

func emaWilder(values []float64, length int) []float64 {
	n := len(values)
	out := make([]float64, n)
	for i := 0; i < n; i++ {
		out[i] = math.NaN()
	}
	if n < length {
		return out
	}
	sum := 0.0
	for i := 0; i < length; i++ {
		sum += values[i]
	}
	out[length-1] = sum / float64(length)
	for i := length; i < n; i++ {
		out[i] = (out[i-1]*float64(length-1) + values[i]) / float64(length)
	}
	return out
}

func rollingMinAt(values []float64, end, length int) float64 {
	start := end - length + 1
	m := values[start]
	for i := start + 1; i <= end; i++ {
		if values[i] < m {
			m = values[i]
		}
	}
	return m
}

func rollingMaxAt(values []float64, end, length int) float64 {
	start := end - length + 1
	m := values[start]
	for i := start + 1; i <= end; i++ {
		if values[i] > m {
			m = values[i]
		}
	}
	return m
}

func rollingMeanAt(values []float64, end, length int) float64 {
	start := end - length + 1
	sum := 0.0
	for i := start; i <= end; i++ {
		sum += values[i]
	}
	return sum / float64(length)
}

func rollingStdAt(values []float64, end, length int) float64 {
	mean := rollingMeanAt(values, end, length)
	start := end - length + 1
	var sum float64
	for i := start; i <= end; i++ {
		d := values[i] - mean
		sum += d * d
	}
	return math.Sqrt(sum / float64(length))
}
