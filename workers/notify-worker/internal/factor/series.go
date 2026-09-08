package factor

import "math"

func finite(v float64, def float64) float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return def
	}
	return v
}

func ratio(num, den float64) float64 {
	if den == 0 {
		return 0
	}
	return num / den
}

func last(xs []float64) float64 {
	if len(xs) == 0 {
		return 0
	}
	return xs[len(xs)-1]
}

func clamp(v, lo, hi float64) float64 {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func roundN(v float64, n int) float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return 0
	}
	p := math.Pow(10, float64(n))
	return math.Round(v*p) / p
}

func rollingMean(xs []float64, length int) float64 {
	if length <= 0 || len(xs) < length {
		return 0
	}
	sum := 0.0
	for i := len(xs) - length; i < len(xs); i++ {
		sum += xs[i]
	}
	return sum / float64(length)
}

func rollingStd(xs []float64, length int) float64 {
	if length <= 1 || len(xs) < length {
		return 0
	}
	mean := rollingMean(xs, length)
	sum := 0.0
	for i := len(xs) - length; i < len(xs); i++ {
		d := xs[i] - mean
		sum += d * d
	}
	return math.Sqrt(sum / float64(length-1))
}

func rollingMin(xs []float64, length int) float64 {
	if length <= 0 || len(xs) < length {
		if len(xs) == 0 {
			return 0
		}
		return minSlice(xs)
	}
	m := xs[len(xs)-length]
	for i := len(xs) - length + 1; i < len(xs); i++ {
		if xs[i] < m {
			m = xs[i]
		}
	}
	return m
}

func rollingMax(xs []float64, length int) float64 {
	if length <= 0 || len(xs) < length {
		if len(xs) == 0 {
			return 0
		}
		return maxSlice(xs)
	}
	m := xs[len(xs)-length]
	for i := len(xs) - length + 1; i < len(xs); i++ {
		if xs[i] > m {
			m = xs[i]
		}
	}
	return m
}

func minSlice(xs []float64) float64 {
	m := xs[0]
	for _, v := range xs[1:] {
		if v < m {
			m = v
		}
	}
	return m
}

func maxSlice(xs []float64) float64 {
	m := xs[0]
	for _, v := range xs[1:] {
		if v > m {
			m = v
		}
	}
	return m
}

func ewmaLast(xs []float64, span int) float64 {
	if len(xs) == 0 || span <= 0 {
		return 0
	}
	alpha := 2.0 / (float64(span) + 1)
	out := xs[0]
	for i := 1; i < len(xs); i++ {
		out = alpha*xs[i] + (1-alpha)*out
	}
	return out
}

func rsiSMA(close []float64, length int) float64 {
	if len(close) < length+1 {
		return 50
	}
	var gain, loss float64
	start := len(close) - length
	for i := start; i < len(close); i++ {
		d := close[i] - close[i-1]
		if d > 0 {
			gain += d
		} else {
			loss -= d
		}
	}
	gain /= float64(length)
	loss /= float64(length)
	if loss == 0 {
		return 100
	}
	rs := gain / loss
	return 100 - 100/(1+rs)
}

func rsiEWM(close []float64, length int) []float64 {
	out := make([]float64, len(close))
	if len(close) < 2 {
		return out
	}
	alpha := 1.0 / float64(length)
	var avgGain, avgLoss float64
	for i := 1; i < len(close); i++ {
		d := close[i] - close[i-1]
		gain, loss := 0.0, 0.0
		if d > 0 {
			gain = d
		} else {
			loss = -d
		}
		if i == 1 {
			avgGain, avgLoss = gain, loss
		} else {
			avgGain = alpha*gain + (1-alpha)*avgGain
			avgLoss = alpha*loss + (1-alpha)*avgLoss
		}
		if i >= length {
			if avgLoss == 0 {
				out[i] = 100
			} else {
				rs := avgGain / avgLoss
				out[i] = 100 - 100/(1+rs)
			}
		}
	}
	return out
}

func periodReturn(close []float64, period int) float64 {
	if len(close) <= period {
		return 0
	}
	base := close[len(close)-1-period]
	return ratio(close[len(close)-1]-base, base) * 100
}

func pctChange(close []float64) []float64 {
	out := make([]float64, len(close))
	for i := 1; i < len(close); i++ {
		if close[i-1] != 0 {
			out[i] = (close[i] - close[i-1]) / close[i-1]
		}
	}
	return out
}

func volatility(close []float64, length int) float64 {
	rets := pctChange(close)
	if len(rets) < 2 {
		return 0
	}
	n := length
	if n > len(rets) {
		n = len(rets)
	}
	tail := rets[len(rets)-n:]
	valid := 0
	for _, v := range tail {
		if v != 0 || valid > 0 {
			valid++
		}
	}
	if len(tail) < 2 {
		return 0
	}
	return rollingStd(tail, len(tail)) * 100
}

func downsideVol(close []float64, length int) float64 {
	rets := pctChange(close)
	if length > len(rets) {
		length = len(rets)
	}
	neg := []float64{}
	for i := len(rets) - length; i < len(rets); i++ {
		if i >= 0 && rets[i] < 0 {
			neg = append(neg, rets[i])
		}
	}
	if len(neg) < 2 {
		return 0
	}
	return rollingStd(neg, len(neg)) * 100
}

func maxDrawdown(close []float64, length int) float64 {
	if length > len(close) {
		length = len(close)
	}
	if length == 0 {
		return 0
	}
	window := close[len(close)-length:]
	runMax := window[0]
	minDD := 0.0
	for _, v := range window {
		if v > runMax {
			runMax = v
		}
		if runMax != 0 {
			dd := (v - runMax) / runMax
			if dd < minDD {
				minDD = dd
			}
		}
	}
	return minDD * 100
}

func corrTail(a, b []float64, length int) float64 {
	if len(a) < 2 || len(b) < 2 {
		return 0
	}
	n := length
	if n > len(a) {
		n = len(a)
	}
	if n > len(b) {
		n = len(b)
	}
	if n < 2 {
		return 0
	}
	aa := a[len(a)-n:]
	bb := b[len(b)-n:]
	ma := rollingMean(aa, n)
	mb := rollingMean(bb, n)
	var num, da, db float64
	for i := 0; i < n; i++ {
		x := aa[i] - ma
		y := bb[i] - mb
		num += x * y
		da += x * x
		db += y * y
	}
	den := math.Sqrt(da * db)
	if den == 0 {
		return 0
	}
	return num / den
}

func pearson(a, b []float64) float64 {
	if len(a) != len(b) || len(a) < 2 {
		return math.NaN()
	}
	return corrTail(a, b, len(a))
}

func rank(xs []float64) []float64 {
	n := len(xs)
	out := make([]float64, n)
	type pair struct {
		i int
		v float64
	}
	ps := make([]pair, n)
	for i, v := range xs {
		ps[i] = pair{i, v}
	}
	// insertion sort by value
	for i := 1; i < n; i++ {
		j := i
		for j > 0 && ps[j-1].v > ps[j].v {
			ps[j-1], ps[j] = ps[j], ps[j-1]
			j--
		}
	}
	for rankIdx, p := range ps {
		out[p.i] = float64(rankIdx + 1)
	}
	return out
}

func rollingCorrLast(a, b []float64, window int) float64 {
	return corrTail(a, b, window)
}

func rollingCovLast(a, b []float64, window int) float64 {
	if len(a) < 2 || len(b) < 2 {
		return 0
	}
	n := window
	if n > len(a) {
		n = len(a)
	}
	if n > len(b) {
		n = len(b)
	}
	if n < 2 {
		return 0
	}
	aa := a[len(a)-n:]
	bb := b[len(b)-n:]
	ma := rollingMean(aa, n)
	mb := rollingMean(bb, n)
	var sum float64
	for i := 0; i < n; i++ {
		sum += (aa[i] - ma) * (bb[i] - mb)
	}
	return sum / float64(n-1)
}

func tsRankLast(xs []float64, window int) float64 {
	if len(xs) == 0 {
		return 0
	}
	n := window
	if n > len(xs) {
		n = len(xs)
	}
	win := xs[len(xs)-n:]
	lastV := win[len(win)-1]
	// searchsorted(sort(arr), arr[-1], side='right') / len
	sorted := append([]float64(nil), win...)
	for i := 1; i < len(sorted); i++ {
		j := i
		for j > 0 && sorted[j-1] > sorted[j] {
			sorted[j-1], sorted[j] = sorted[j], sorted[j-1]
			j--
		}
	}
	count := 0
	for _, v := range sorted {
		if v <= lastV {
			count++
		}
	}
	return float64(count) / float64(len(win))
}

func argMaxLast(xs []float64, window int) float64 {
	if len(xs) == 0 {
		return 0
	}
	n := window
	if n > len(xs) {
		n = len(xs)
	}
	win := xs[len(xs)-n:]
	idx := 0
	m := win[0]
	for i, v := range win {
		if v > m {
			m = v
			idx = i
		}
	}
	return float64(idx)
}

func argMinLast(xs []float64, window int) float64 {
	if len(xs) == 0 {
		return 0
	}
	n := window
	if n > len(xs) {
		n = len(xs)
	}
	win := xs[len(xs)-n:]
	idx := 0
	m := win[0]
	for i, v := range win {
		if v < m {
			m = v
			idx = i
		}
	}
	return float64(idx)
}

func slopeLast(xs []float64, window int) float64 {
	if len(xs) < 3 {
		return 0
	}
	n := window
	if n > len(xs) {
		n = len(xs)
	}
	if n < 3 {
		return 0
	}
	win := xs[len(xs)-n:]
	same := true
	for i := 1; i < n; i++ {
		if win[i] != win[0] {
			same = false
			break
		}
	}
	if same {
		return 0
	}
	meanX := 0.0
	for i := 0; i < n; i++ {
		meanX += float64(i)
	}
	meanX /= float64(n)
	meanY := rollingMean(win, n)
	var num, den float64
	for i := 0; i < n; i++ {
		x := float64(i) - meanX
		y := win[i] - meanY
		num += x * y
		den += x * x
	}
	if den == 0 {
		return 0
	}
	return num / den
}

func rsquareLast(xs []float64, window int) float64 {
	if len(xs) < 3 {
		return 0
	}
	n := window
	if n > len(xs) {
		n = len(xs)
	}
	if n < 3 {
		return 0
	}
	win := xs[len(xs)-n:]
	same := true
	for i := 1; i < n; i++ {
		if win[i] != win[0] {
			same = false
			break
		}
	}
	if same {
		return 0
	}
	meanX := 0.0
	for i := 0; i < n; i++ {
		meanX += float64(i)
	}
	meanX /= float64(n)
	meanY := rollingMean(win, n)
	var xy, xx, yy float64
	for i := 0; i < n; i++ {
		x := float64(i) - meanX
		y := win[i] - meanY
		xy += x * y
		xx += x * x
		yy += y * y
	}
	den := xx * yy
	if den <= 0 {
		return 0
	}
	return (xy * xy) / den
}

func sign(v float64) float64 {
	if v > 0 {
		return 1
	}
	if v < 0 {
		return -1
	}
	return 0
}

func delay(xs []float64, period int) float64 {
	if period < 0 || len(xs) <= period {
		return 0
	}
	return xs[len(xs)-1-period]
}

func delta(xs []float64, period int) float64 {
	if period < 0 || len(xs) <= period {
		return 0
	}
	return xs[len(xs)-1] - xs[len(xs)-1-period]
}
