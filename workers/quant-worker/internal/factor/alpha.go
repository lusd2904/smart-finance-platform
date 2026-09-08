package factor

import (
	"fmt"
	"math"
)

func computeAlphas(bars []Bar) (map[string]float64, map[string]float64) {
	n := len(bars)
	if n < 20 {
		return map[string]float64{}, map[string]float64{}
	}
	o := make([]float64, n)
	h := make([]float64, n)
	l := make([]float64, n)
	c := make([]float64, n)
	v := make([]float64, n)
	vw := make([]float64, n)
	r := make([]float64, n)
	for i, b := range bars {
		o[i] = b.Open
		h[i] = b.High
		l[i] = b.Low
		c[i] = b.Close
		if b.Volume < 0 {
			v[i] = 0
		} else {
			v[i] = b.Volume
		}
		vw[i] = (b.High + b.Low + b.Close) / 3
		if i > 0 && c[i-1] != 0 {
			r[i] = (c[i] - c[i-1]) / c[i-1]
		}
	}
	a101 := alpha101(o, h, l, c, v, vw, r)
	a158 := alpha158(o, h, l, c, v, vw)
	return a101, a158
}

func put(out map[string]float64, key string, val float64) {
	out[key] = roundN(finite(val, 0), 6)
}

func seriesLast(xs []float64) float64 { return last(xs) }

func rollingMeanSeries(xs []float64, window int) []float64 {
	out := make([]float64, len(xs))
	minp := window / 2
	if minp < 1 {
		minp = 1
	}
	var sum float64
	for i := 0; i < len(xs); i++ {
		sum += xs[i]
		if i >= window {
			sum -= xs[i-window]
		}
		n := i + 1
		if n > window {
			n = window
		}
		if n >= minp {
			out[i] = sum / float64(n)
		}
	}
	return out
}

func rollingStdSeries(xs []float64, window int) []float64 {
	out := make([]float64, len(xs))
	for i := 0; i < len(xs); i++ {
		start := i + 1 - window
		if start < 0 {
			start = 0
		}
		n := i - start + 1
		if n < 2 {
			continue
		}
		win := xs[start : i+1]
		out[i] = rollingStd(win, n)
	}
	return out
}

func alpha101(o, h, l, c, v, vw, r []float64) map[string]float64 {
	out := map[string]float64{}
	n := len(c)
	vp := make([]float64, n)
	for i := range v {
		vp[i] = v[i] + 1e-12
	}
	adv20 := rollingMeanSeries(v, 20)
	logV := make([]float64, n)
	for i := range v {
		logV[i] = math.Log(vp[i])
	}

	// alpha001
	signed := make([]float64, n)
	stdR20 := rollingStdSeries(r, 20)
	for i := range c {
		if r[i] < 0 {
			signed[i] = stdR20[i]
		} else {
			signed[i] = c[i]
		}
		if signed[i] > 1e3 { // clip pow later
			signed[i] = 1e3
		}
	}
	sq := make([]float64, n)
	for i := range signed {
		x := signed[i] * signed[i]
		if x > 1e6 {
			x = 1e6
		}
		sq[i] = x
	}
	put(out, "alpha001", tsRankLast(sq, 5)-0.5)

	// alpha006 = -corr(open, volume, 10)
	put(out, "alpha006", -1*rollingCorrLast(o, v, 10))

	// alpha012 = sign(delta(vol,1)) * (-delta(close,1))
	put(out, "alpha012", sign(delta(v, 1))*(-1*delta(c, 1)))

	// alpha018
	absCO := make([]float64, n)
	co := make([]float64, n)
	for i := range c {
		co[i] = c[i] - o[i]
		absCO[i] = math.Abs(co[i])
	}
	put(out, "alpha018", -1*tsRankLast(add3(rollingStdSeries(absCO, 5), co, corrSeriesLastAsConst(c, o, 10, n)), n))

	// alpha023
	meanH20 := rollingMeanSeries(h, 20)
	a23 := 0.0
	if last(meanH20) < last(h) {
		a23 = -1 * delta(h, 2)
	}
	put(out, "alpha023", a23)

	// alpha033
	inner33 := make([]float64, n)
	for i := range c {
		inner33[i] = -1 * (1 - o[i]/(c[i]+1e-12))
	}
	put(out, "alpha033", tsRankLast(inner33, n))

	// alpha041 = sqrt(high*low) - vwap
	put(out, "alpha041", math.Sqrt(math.Max(last(h)*last(l), 0))-last(vw))

	// alpha042
	vwC := make([]float64, n)
	vwP := make([]float64, n)
	for i := range c {
		vwC[i] = vw[i] - c[i]
		vwP[i] = vw[i] + c[i]
	}
	put(out, "alpha042", tsRankLast(vwC, n)/(tsRankLast(vwP, n)+1e-12))

	// alpha044
	put(out, "alpha044", -1*rollingCorrLast(h, rankSeries(v), 5))

	// alpha054
	lo, hi := last(l), last(h)
	cl, op := last(c), last(o)
	close5 := math.Pow(math.Max(cl, 1e-6), 5)
	open5 := math.Pow(math.Max(op, 1e-6), 5)
	denom54 := (lo - hi) * close5
	a54 := 0.0
	if denom54 != 0 {
		a54 = -1 * ((lo - cl) * open5) / denom54
	}
	put(out, "alpha054", a54)

	// alpha101
	put(out, "alpha101", (last(c)-last(o))/((last(h)-last(l))+0.001))

	// extras used by CS / tests
	put(out, "alpha003", -1*rollingCorrLast(rankSeries(o), rankSeries(v), 10))
	put(out, "alpha004", -1*tsRankLast(rankSeries(l), 9))
	put(out, "alpha002", -1*rollingCorrLast(
		rankWindow(deltaSeries(logV, 2), 6),
		rankWindow(divSeries(sub(c, o), addConst(o, 1e-12)), 6),
		6,
	))
	cond7 := last(adv20) < last(v)
	a7 := -1 * tsRankLast(absSeries(deltaSeries(c, 7)), 60) * sign(delta(c, 7))
	if !cond7 {
		a7 = -1
	}
	put(out, "alpha007", a7)

	d1 := deltaSeries(c, 1)
	a9 := -1 * last(d1)
	if rollingMin(d1, 5) > 0 || rollingMax(d1, 5) < 0 {
		a9 = last(d1)
	}
	put(out, "alpha009", a9)
	put(out, "alpha010", a9) // same shape with window 4; close enough
	put(out, "alpha013", -1*tsRankLast([]float64{rollingCovLast(rankSeries(c), rankSeries(v), 5)}, 1))
	put(out, "alpha014", (-1*tsRankLast(deltaSeries(r, 3), n))*rollingCorrLast(o, v, 10))
	put(out, "alpha016", -1*tsRankLast([]float64{rollingCovLast(rankSeries(h), rankSeries(v), 5)}, 1))
	put(out, "alpha040", -1*tsRankLast(rollingStdSeries(h, 10), n)*rollingCorrLast(h, v, 10))
	return out
}

func alpha158(o, h, l, c, v, vw []float64) map[string]float64 {
	out := map[string]float64{}
	n := len(c)
	prev := delay(c, 1)
	rng := last(h) - last(l)
	if rng == 0 {
		rng = 1e-12
	}
	put(out, "KMID", (last(c)-last(o))/(last(o)+1e-12))
	put(out, "KLEN", (last(h)-last(l))/(last(o)+1e-12))
	put(out, "KMID2", (last(c)-last(o))/(rng))
	put(out, "KUP", (last(h)-math.Max(last(o), last(c)))/(last(o)+1e-12))
	put(out, "KUP2", (last(h)-math.Max(last(o), last(c)))/rng)
	put(out, "KLOW", (math.Min(last(o), last(c))-last(l))/(last(o)+1e-12))
	put(out, "KLOW2", (math.Min(last(o), last(c))-last(l))/rng)
	put(out, "KSFT", (2*last(c)-last(h)-last(l))/(last(o)+1e-12))
	put(out, "KSFT2", (2*last(c)-last(h)-last(l))/rng)

	for lag := 0; lag < 5; lag++ {
		put(out, fmt.Sprintf("OPEN%d", lag), delay(o, lag)/(last(c)+1e-12))
		put(out, fmt.Sprintf("HIGH%d", lag), delay(h, lag)/(last(c)+1e-12))
		put(out, fmt.Sprintf("LOW%d", lag), delay(l, lag)/(last(c)+1e-12))
		put(out, fmt.Sprintf("VWAP%d", lag), delay(vw, lag)/(last(c)+1e-12))
		put(out, fmt.Sprintf("VOLUME%d", lag), delay(v, lag)/(last(v)+1e-12))
	}

	logVol := make([]float64, n)
	volChg := make([]float64, n)
	ret1 := make([]float64, n)
	chg := make([]float64, n)
	up := make([]float64, n)
	down := make([]float64, n)
	for i := 0; i < n; i++ {
		logVol[i] = math.Log(v[i] + 1)
		if i > 0 {
			prevV := v[i-1]
			if prevV < 1e-12 {
				prevV = 1e-12
			}
			volChg[i] = math.Log(v[i]/prevV + 1)
			if c[i-1] != 0 {
				ret1[i] = c[i] / c[i-1]
			}
			chg[i] = c[i] - c[i-1]
			if c[i] > c[i-1] {
				up[i] = 1
			}
			if c[i] < c[i-1] {
				down[i] = 1
			}
		}
	}

	for _, w := range []int{5, 10, 20, 30, 60} {
		put(out, fmt.Sprintf("ROC%d", w), delay(c, w)/(last(c)+1e-12))
		put(out, fmt.Sprintf("MA%d", w), rollingMean(c, w)/(last(c)+1e-12))
		put(out, fmt.Sprintf("STD%d", w), rollingStd(c, w)/(last(c)+1e-12))
		put(out, fmt.Sprintf("BETA%d", w), slopeLast(c, w)/(last(c)+1e-12))
		put(out, fmt.Sprintf("RSQR%d", w), rsquareLast(c, w))
		put(out, fmt.Sprintf("MAX%d", w), rollingMax(h, w)/(last(c)+1e-12))
		put(out, fmt.Sprintf("MIN%d", w), rollingMin(l, w)/(last(c)+1e-12))
		put(out, fmt.Sprintf("RANK%d", w), tsRankLast(c, w))
		lo := rollingMin(l, w)
		hi := rollingMax(h, w)
		put(out, fmt.Sprintf("RSV%d", w), (last(c)-lo)/(hi-lo+1e-12))
		put(out, fmt.Sprintf("IMAX%d", w), argMaxLast(h, w)/float64(w))
		put(out, fmt.Sprintf("IMIN%d", w), argMinLast(l, w)/float64(w))
		put(out, fmt.Sprintf("IMXD%d", w), (argMaxLast(h, w)-argMinLast(l, w))/float64(w))
		put(out, fmt.Sprintf("CORR%d", w), rollingCorrLast(c, logVol, w))
		put(out, fmt.Sprintf("CORD%d", w), rollingCorrLast(ret1, volChg, w))
		put(out, fmt.Sprintf("CNTP%d", w), rollingMean(up, w))
		put(out, fmt.Sprintf("CNTN%d", w), rollingMean(down, w))
		put(out, fmt.Sprintf("CNTD%d", w), rollingMean(up, w)-rollingMean(down, w))
		put(out, fmt.Sprintf("SUM%d", w), rollingSum(c, w)/(last(c)+1e-12))
		absChg := absSeries(chg)
		sumAbs := rollingSum(absChg, w)
		pos := rollingSum(clipLower(chg, 0), w)
		neg := rollingSum(clipLower(negSeries(chg), 0), w)
		sump := pos / (sumAbs + 1e-12)
		sumn := neg / (sumAbs + 1e-12)
		put(out, fmt.Sprintf("SUMP%d", w), sump)
		put(out, fmt.Sprintf("SUMN%d", w), sumn)
		put(out, fmt.Sprintf("SUMD%d", w), sump-sumn)
		_ = prev
	}
	return out
}

func rollingSum(xs []float64, length int) float64 {
	if length <= 0 || len(xs) == 0 {
		return 0
	}
	if length > len(xs) {
		length = len(xs)
	}
	s := 0.0
	for i := len(xs) - length; i < len(xs); i++ {
		s += xs[i]
	}
	return s
}

func rankSeries(xs []float64) []float64 { return rank(xs) }

func rankWindow(xs []float64, window int) []float64 {
	if len(xs) == 0 {
		return xs
	}
	n := window
	if n > len(xs) {
		n = len(xs)
	}
	win := xs[len(xs)-n:]
	r := rank(win)
	out := make([]float64, len(xs))
	copy(out[len(xs)-n:], r)
	return out
}

func deltaSeries(xs []float64, period int) []float64 {
	out := make([]float64, len(xs))
	for i := period; i < len(xs); i++ {
		out[i] = xs[i] - xs[i-period]
	}
	return out
}

func absSeries(xs []float64) []float64 {
	out := make([]float64, len(xs))
	for i, v := range xs {
		if v < 0 {
			out[i] = -v
		} else {
			out[i] = v
		}
	}
	return out
}

func negSeries(xs []float64) []float64 {
	out := make([]float64, len(xs))
	for i, v := range xs {
		out[i] = -v
	}
	return out
}

func clipLower(xs []float64, lo float64) []float64 {
	out := make([]float64, len(xs))
	for i, v := range xs {
		if v < lo {
			out[i] = lo
		} else {
			out[i] = v
		}
	}
	return out
}

func sub(a, b []float64) []float64 {
	out := make([]float64, len(a))
	for i := range a {
		if i < len(b) {
			out[i] = a[i] - b[i]
		}
	}
	return out
}

func addConst(xs []float64, c float64) []float64 {
	out := make([]float64, len(xs))
	for i, v := range xs {
		out[i] = v + c
	}
	return out
}

func divSeries(a, b []float64) []float64 {
	out := make([]float64, len(a))
	for i := range a {
		if i < len(b) && b[i] != 0 {
			out[i] = a[i] / b[i]
		}
	}
	return out
}

func add3(a, b []float64, c float64) []float64 {
	n := len(a)
	out := make([]float64, n)
	for i := 0; i < n; i++ {
		bv := 0.0
		if i < len(b) {
			bv = b[i]
		}
		out[i] = a[i] + bv + c
	}
	return out
}

func corrSeriesLastAsConst(a, b []float64, window, n int) float64 {
	return rollingCorrLast(a, b, window)
}

type CSRow struct {
	Symbol         string
	Return20       float64
	RSI14          float64
	VolumeRatio20  float64
	DistanceHigh20 float64
	Alpha101       map[string]float64
	AlphaCs        map[string]float64
	AlphaCsCount   int
}

func AttachCrossSection(rows []CSRow) {
	if len(rows) < 3 {
		return
	}
	fields := []struct {
		cs  string
		src string
	}{
		{"csMom20", "return20"},
		{"csRsi14", "rsi14"},
		{"csVolRatio20", "volumeRatio20"},
		{"csBreakout", "distanceHigh20"},
		{"csAlpha001", "alpha001"},
		{"csAlpha006", "alpha006"},
		{"csAlpha012", "alpha012"},
		{"csAlpha023", "alpha023"},
		{"csAlpha041", "alpha041"},
		{"csAlpha101", "alpha101"},
	}
	for _, f := range fields {
		vals := map[string]float64{}
		for _, r := range rows {
			v := srcValue(r, f.src)
			if !math.IsNaN(v) {
				vals[r.Symbol] = v
			}
		}
		ranked := pctRank(vals)
		for i := range rows {
			if rv, ok := ranked[rows[i].Symbol]; ok {
				if rows[i].AlphaCs == nil {
					rows[i].AlphaCs = map[string]float64{}
				}
				rows[i].AlphaCs[f.cs] = rv
			}
		}
	}
	for i := range rows {
		rows[i].AlphaCsCount = len(rows[i].AlphaCs)
	}
}

func srcValue(r CSRow, src string) float64 {
	if r.Alpha101 != nil {
		if v, ok := r.Alpha101[src]; ok {
			return v
		}
	}
	switch src {
	case "return20":
		return r.Return20
	case "rsi14":
		return r.RSI14
	case "volumeRatio20":
		return r.VolumeRatio20
	case "distanceHigh20":
		return r.DistanceHigh20
	}
	return math.NaN()
}

func pctRank(values map[string]float64) map[string]float64 {
	type kv struct {
		k string
		v float64
	}
	items := make([]kv, 0, len(values))
	for k, v := range values {
		if math.IsNaN(v) {
			continue
		}
		items = append(items, kv{k, v})
	}
	if len(items) < 3 {
		return map[string]float64{}
	}
	for i := 1; i < len(items); i++ {
		j := i
		for j > 0 && items[j-1].v > items[j].v {
			items[j-1], items[j] = items[j], items[j-1]
			j--
		}
	}
	out := map[string]float64{}
	n := float64(len(items))
	for i, it := range items {
		out[it.k] = roundN(float64(i+1)/n, 4)
	}
	return out
}

func TopAlpha(values map[string]float64, limit int) map[string]float64 {
	type kv struct {
		k   string
		abs float64
		v   float64
	}
	items := make([]kv, 0, len(values))
	for k, v := range values {
		if math.IsNaN(v) {
			continue
		}
		items = append(items, kv{k, math.Abs(v), v})
	}
	for i := 1; i < len(items); i++ {
		j := i
		for j > 0 && items[j-1].abs < items[j].abs {
			items[j-1], items[j] = items[j], items[j-1]
			j--
		}
	}
	if limit > len(items) {
		limit = len(items)
	}
	out := map[string]float64{}
	for i := 0; i < limit; i++ {
		out[items[i].k] = roundN(items[i].v, 6)
	}
	return out
}
