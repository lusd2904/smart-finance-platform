// Package factorqc ports Alphalens-style IC / IR / quantile checks.
package factorqc

import (
	"math"
	"sort"
)

const (
	EngineVersion    = "alphalens-style-v1"
	MinCrossSection  = 8
	MinICDates       = 20
	Quantiles        = 5
)

var Periods = []int{1, 5, 10}

type Panel struct {
	Dates   []string
	Symbols []string
	Close   [][]float64 // [date][symbol], NaN if missing
	Volume  [][]float64
}

type HorizonRow struct {
	Horizon          int                `json:"horizon"`
	ICMean           *float64           `json:"icMean"`
	ICStd            *float64           `json:"icStd"`
	IR               *float64           `json:"ir"`
	ICPositiveRatio  *float64           `json:"icPositiveRatio"`
	SampleDates      int                `json:"sampleDates"`
	SymbolCount      int                `json:"symbolCount"`
	Quantiles        map[string]float64 `json:"quantiles"`
	Spread           *float64           `json:"spread"`
	OK               bool               `json:"ok"`
}

type Item struct {
	FactorKey   string `json:"factorKey"`
	FactorLabel string `json:"factorLabel"`
	Family      string `json:"family"`
	HorizonRow
}

type Report struct {
	OK          bool     `json:"ok"`
	Engine      string   `json:"engine"`
	Market      string   `json:"market"`
	AsOf        string   `json:"asOf"`
	SymbolCount int      `json:"symbolCount"`
	ItemCount   int      `json:"itemCount"`
	OKCount     int      `json:"okCount"`
	Periods     []int    `json:"periods"`
	Message     string   `json:"message"`
	Items       []Item   `json:"items"`
	Saved       int      `json:"saved,omitempty"`
}

type Spec struct {
	Key    string
	Label  string
	Family string
	Func   func(p Panel) [][]float64
}

func finitePtr(v float64) *float64 {
	if math.IsNaN(v) || math.IsInf(v, 0) {
		return nil
	}
	x := v
	return &x
}

func round4(v float64) float64 {
	return math.Round(v*10000) / 10000
}

func KlinesToPanel(symbolKlines map[string][]struct {
	Date   string
	Close  float64
	Volume float64
}) Panel {
	dateSet := map[string]struct{}{}
	symbols := make([]string, 0, len(symbolKlines))
	for sym, rows := range symbolKlines {
		if len(rows) == 0 {
			continue
		}
		symbols = append(symbols, sym)
		for _, r := range rows {
			if r.Date != "" {
				dateSet[r.Date] = struct{}{}
			}
		}
	}
	sort.Strings(symbols)
	dates := make([]string, 0, len(dateSet))
	for d := range dateSet {
		dates = append(dates, d)
	}
	sort.Strings(dates)
	closeM := make([][]float64, len(dates))
	volM := make([][]float64, len(dates))
	idx := map[string]int{}
	for i, d := range dates {
		idx[d] = i
		closeM[i] = nans(len(symbols))
		volM[i] = nans(len(symbols))
	}
	symIdx := map[string]int{}
	for i, s := range symbols {
		symIdx[s] = i
	}
	for sym, rows := range symbolKlines {
		j, ok := symIdx[sym]
		if !ok {
			continue
		}
		seen := map[string]struct{}{}
		for _, r := range rows {
			i, ok := idx[r.Date]
			if !ok {
				continue
			}
			if _, dup := seen[r.Date]; dup {
				continue
			}
			seen[r.Date] = struct{}{}
			closeM[i][j] = r.Close
			volM[i][j] = r.Volume
		}
	}
	return Panel{Dates: dates, Symbols: symbols, Close: closeM, Volume: volM}
}

func nans(n int) []float64 {
	out := make([]float64, n)
	for i := range out {
		out[i] = math.NaN()
	}
	return out
}

func pctChange(panel [][]float64, period int) [][]float64 {
	out := make([][]float64, len(panel))
	for i := range panel {
		out[i] = nans(len(panel[i]))
		if i < period {
			continue
		}
		for j := range panel[i] {
			prev := panel[i-period][j]
			cur := panel[i][j]
			if math.IsNaN(prev) || math.IsNaN(cur) || prev == 0 {
				continue
			}
			out[i][j] = (cur - prev) / prev
		}
	}
	return out
}

func shiftNeg(panel [][]float64, period int) [][]float64 {
	out := make([][]float64, len(panel))
	for i := range panel {
		out[i] = nans(len(panel[i]))
		src := i + period
		if src >= len(panel) {
			continue
		}
		copy(out[i], panel[src])
	}
	return out
}

func ForwardReturns(close [][]float64, period int) [][]float64 {
	return shiftNeg(pctChange(close, period), period)
}

func spearman(left, right []float64) *float64 {
	xs, ys := []float64{}, []float64{}
	for i := 0; i < len(left) && i < len(right); i++ {
		if math.IsNaN(left[i]) || math.IsNaN(right[i]) {
			continue
		}
		xs = append(xs, left[i])
		ys = append(ys, right[i])
	}
	if len(xs) < MinCrossSection {
		return nil
	}
	rx := ranks(xs)
	ry := ranks(ys)
	return finitePtr(pearson(rx, ry))
}

func ranks(xs []float64) []float64 {
	type pair struct {
		i int
		v float64
	}
	ps := make([]pair, len(xs))
	for i, v := range xs {
		ps[i] = pair{i, v}
	}
	sort.Slice(ps, func(i, j int) bool { return ps[i].v < ps[j].v })
	out := make([]float64, len(xs))
	for r, p := range ps {
		out[p.i] = float64(r + 1)
	}
	return out
}

func pearson(a, b []float64) float64 {
	n := len(a)
	if n != len(b) || n < 2 {
		return math.NaN()
	}
	var ma, mb float64
	for i := 0; i < n; i++ {
		ma += a[i]
		mb += b[i]
	}
	ma /= float64(n)
	mb /= float64(n)
	var num, da, db float64
	for i := 0; i < n; i++ {
		x := a[i] - ma
		y := b[i] - mb
		num += x * y
		da += x * x
		db += y * y
	}
	den := math.Sqrt(da * db)
	if den == 0 {
		return math.NaN()
	}
	return num / den
}

func DailyIC(factor, fwd [][]float64) []float64 {
	ics := []float64{}
	n := len(factor)
	if len(fwd) < n {
		n = len(fwd)
	}
	for i := 0; i < n; i++ {
		ic := spearman(factor[i], fwd[i])
		if ic != nil {
			ics = append(ics, *ic)
		}
	}
	return ics
}

func QuantileMeans(factor, fwd [][]float64, q int) map[string]float64 {
	type pair struct{ f, r float64 }
	var rows []pair
	for i := range factor {
		if i >= len(fwd) {
			break
		}
		for j := range factor[i] {
			if j >= len(fwd[i]) {
				break
			}
			if math.IsNaN(factor[i][j]) || math.IsNaN(fwd[i][j]) {
				continue
			}
			rows = append(rows, pair{factor[i][j], fwd[i][j]})
		}
	}
	if len(rows) == 0 {
		return map[string]float64{}
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].f < rows[j].f })
	uniq := map[float64]struct{}{}
	for _, r := range rows {
		uniq[r.f] = struct{}{}
	}
	if len(uniq) < q {
		return map[string]float64{}
	}
	// equal-count bins (qcut duplicates='drop' approximation)
	means := make([]float64, q)
	counts := make([]int, q)
	for i, r := range rows {
		bin := i * q / len(rows)
		if bin >= q {
			bin = q - 1
		}
		means[bin] += r.r
		counts[bin]++
	}
	out := map[string]float64{}
	var first, last *float64
	for i := 0; i < q; i++ {
		if counts[i] == 0 {
			continue
		}
		m := means[i] / float64(counts[i])
		key := "q" + itoa(i+1)
		out[key] = round4(m * 100)
		if first == nil {
			x := m
			first = &x
		}
		x := m
		last = &x
	}
	if first != nil && last != nil {
		out["spread"] = round4((*last - *first) * 100)
	}
	return out
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	s := ""
	for n > 0 {
		s = string(rune('0'+n%10)) + s
		n /= 10
	}
	return s
}

func EvaluateFactor(factor, close [][]float64, periods []int) []HorizonRow {
	if periods == nil {
		periods = Periods
	}
	symCount := 0
	if len(close) > 0 {
		symCount = len(close[0])
	}
	rows := make([]HorizonRow, 0, len(periods))
	for _, p := range periods {
		fwd := ForwardReturns(close, p)
		ics := DailyIC(factor, fwd)
		qstats := QuantileMeans(factor, fwd, Quantiles)
		var icMean, icStd *float64
		var ir *float64
		if len(ics) > 0 {
			m := mean(ics)
			icMean = finitePtr(round4(m))
			if len(ics) > 1 {
				s := stdSample(ics)
				icStd = finitePtr(round4(s))
				if s != 0 && math.Abs(s) > 1e-12 {
					v := round4(m / s)
					ir = &v
				}
			}
		}
		var pos *float64
		if len(ics) > 0 {
			c := 0
			for _, v := range ics {
				if v > 0 {
					c++
				}
			}
			x := round4(float64(c) / float64(len(ics)))
			pos = &x
		}
		var spread *float64
		if s, ok := qstats["spread"]; ok {
			spread = &s
		}
		rows = append(rows, HorizonRow{
			Horizon:         p,
			ICMean:          icMean,
			ICStd:           icStd,
			IR:              ir,
			ICPositiveRatio: pos,
			SampleDates:     len(ics),
			SymbolCount:     symCount,
			Quantiles:       qstats,
			Spread:          spread,
			OK:              len(ics) >= MinICDates && icMean != nil,
		})
	}
	return rows
}

func mean(xs []float64) float64 {
	s := 0.0
	for _, v := range xs {
		s += v
	}
	return s / float64(len(xs))
}

func stdSample(xs []float64) float64 {
	if len(xs) < 2 {
		return math.NaN()
	}
	m := mean(xs)
	s := 0.0
	for _, v := range xs {
		d := v - m
		s += d * d
	}
	return math.Sqrt(s / float64(len(xs)-1))
}

func rollingMeanCol(panel [][]float64, window int) [][]float64 {
	out := make([][]float64, len(panel))
	cols := 0
	if len(panel) > 0 {
		cols = len(panel[0])
	}
	for i := range panel {
		out[i] = nans(cols)
		start := i + 1 - window
		if start < 0 {
			start = 0
		}
		for j := 0; j < cols; j++ {
			sum, n := 0.0, 0
			ok := true
			for k := start; k <= i; k++ {
				if math.IsNaN(panel[k][j]) {
					ok = false
					break
				}
				sum += panel[k][j]
				n++
			}
			if ok && n == window {
				out[i][j] = sum / float64(n)
			}
		}
	}
	return out
}

func rsiPanel(close [][]float64, length int) [][]float64 {
	rows := len(close)
	cols := 0
	if rows > 0 {
		cols = len(close[0])
	}
	out := make([][]float64, rows)
	alpha := 1.0 / float64(length)
	avgG := make([]float64, cols)
	avgL := make([]float64, cols)
	for i := range out {
		out[i] = nans(cols)
		if i == 0 {
			continue
		}
		for j := 0; j < cols; j++ {
			if math.IsNaN(close[i][j]) || math.IsNaN(close[i-1][j]) {
				continue
			}
			d := close[i][j] - close[i-1][j]
			gain, loss := 0.0, 0.0
			if d > 0 {
				gain = d
			} else {
				loss = -d
			}
			if i == 1 {
				avgG[j], avgL[j] = gain, loss
			} else {
				avgG[j] = alpha*gain + (1-alpha)*avgG[j]
				avgL[j] = alpha*loss + (1-alpha)*avgL[j]
			}
			if i >= length {
				if avgL[j] == 0 {
					out[i][j] = 100
				} else {
					rs := avgG[j] / avgL[j]
					out[i][j] = 100 - 100/(1+rs)
				}
			}
		}
	}
	return out
}

func rankAxis1(panel [][]float64) [][]float64 {
	out := make([][]float64, len(panel))
	for i, row := range panel {
		out[i] = nans(len(row))
		vals := []float64{}
		idx := []int{}
		for j, v := range row {
			if math.IsNaN(v) {
				continue
			}
			vals = append(vals, v)
			idx = append(idx, j)
		}
		if len(vals) < 2 {
			continue
		}
		r := ranks(vals)
		n := float64(len(vals))
		for k, j := range idx {
			out[i][j] = r[k] / n
		}
	}
	return out
}

func DefaultSpecs() []Spec {
	return []Spec{
		{"mom20", "20日动量", "momentum", func(p Panel) [][]float64 { return pctChange(p.Close, 20) }},
		{"reversal5", "5日反转", "reversion", func(p Panel) [][]float64 {
			m := pctChange(p.Close, 5)
			for i := range m {
				for j := range m[i] {
					if !math.IsNaN(m[i][j]) {
						m[i][j] = -m[i][j]
					}
				}
			}
			return m
		}},
		{"rsi14", "RSI14", "momentum", func(p Panel) [][]float64 { return rsiPanel(p.Close, 14) }},
		{"ma_spread", "均线差 MA20/MA60", "trend", func(p Panel) [][]float64 {
			ma20 := rollingMeanCol(p.Close, 20)
			ma60 := rollingMeanCol(p.Close, 60)
			out := make([][]float64, len(p.Close))
			for i := range p.Close {
				out[i] = nans(len(p.Symbols))
				for j := range p.Symbols {
					if !math.IsNaN(ma20[i][j]) && !math.IsNaN(ma60[i][j]) && ma60[i][j] != 0 {
						out[i][j] = ma20[i][j]/ma60[i][j] - 1
					}
				}
			}
			return out
		}},
		{"vol_ratio20", "量比20", "volumeFlow", func(p Panel) [][]float64 {
			ma := rollingMeanCol(p.Volume, 20)
			out := make([][]float64, len(p.Volume))
			for i := range p.Volume {
				out[i] = nans(len(p.Symbols))
				for j := range p.Symbols {
					if !math.IsNaN(p.Volume[i][j]) && !math.IsNaN(ma[i][j]) && ma[i][j] != 0 {
						out[i][j] = p.Volume[i][j] / ma[i][j]
					}
				}
			}
			return out
		}},
		{"cs_mom20", "Alpha101 截面动量 rank", "alpha101Cs", func(p Panel) [][]float64 {
			return rankAxis1(pctChange(p.Close, 20))
		}},
		{"cs_vol_ratio", "Alpha101 截面量比 rank", "alpha101Cs", func(p Panel) [][]float64 {
			ma := rollingMeanCol(p.Volume, 20)
			ratio := make([][]float64, len(p.Volume))
			for i := range p.Volume {
				ratio[i] = nans(len(p.Symbols))
				for j := range p.Symbols {
					if !math.IsNaN(p.Volume[i][j]) && !math.IsNaN(ma[i][j]) && ma[i][j] != 0 {
						ratio[i][j] = p.Volume[i][j] / ma[i][j]
					}
				}
			}
			return rankAxis1(ratio)
		}},
	}
}

func ComputeReport(p Panel, market string) Report {
	if len(p.Symbols) < MinCrossSection {
		return Report{
			OK: false, Engine: EngineVersion, Market: market,
			Message:     "截面标的不足（需至少 8 只，当前 " + itoa(len(p.Symbols)) + "）",
			Items:       []Item{},
			SymbolCount: len(p.Symbols),
		}
	}
	asOf := ""
	if len(p.Dates) > 0 {
		asOf = p.Dates[len(p.Dates)-1]
	}
	items := []Item{}
	for _, spec := range DefaultSpecs() {
		fac := spec.Func(p)
		for _, row := range EvaluateFactor(fac, p.Close, Periods) {
			items = append(items, Item{
				FactorKey: spec.Key, FactorLabel: spec.Label, Family: spec.Family,
				HorizonRow: row,
			})
		}
	}
	okCount := 0
	for _, it := range items {
		if it.OK {
			okCount++
		}
	}
	msg := "质检完成"
	if okCount == 0 {
		msg = "样本日期不足，IC 结果仅供参考"
	}
	return Report{
		OK: okCount > 0, Engine: EngineVersion, Market: market, AsOf: asOf,
		SymbolCount: len(p.Symbols), ItemCount: len(items), OKCount: okCount,
		Periods: Periods, Message: msg, Items: items,
	}
}
