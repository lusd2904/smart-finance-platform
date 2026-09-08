package heat

import (
	"fmt"
	"math"
	"sort"
	"strings"
)

const (
	activeHeatScore    = 70.0
	coldHeatScore      = 35.0
	breadthFlatBandPct = 0.05
)

type Candidate struct {
	Symbol        string
	Name          string
	MarketCap     *float64
	Turnover      *float64
	ChangePct     *float64
	Last          *float64
	ChangeAmount  *float64
	TurnoverRate  *float64
	VolumeRatio   *float64
	Amplitude     *float64
	PE            *float64
	MainNetInflow *float64
	Currency      string
}

type Extras struct {
	Source        []string
	IndexChange   *float64
	Advance       *int
	Decline       *int
	Flat          *int
	IndexTurnover *float64
}

type Top50Item struct {
	RankNo        int
	Symbol        string
	Name          string
	MarketCap     *float64
	Turnover      *float64
	ChangePct     *float64
	Last          *float64
	ChangeAmount  *float64
	TurnoverRate  *float64
	VolumeRatio   *float64
	Amplitude     *float64
	PE            *float64
	MainNetInflow *float64
	Currency      string
}

type CollectResult struct {
	Skipped        bool
	Reason         string
	Market         string
	TradeDate      string
	HeatScore      float64
	Summary        string
	IndexChange    *float64
	TotalTurnover  *float64
	Advance        int
	Decline        int
	Flat           int
	Top50          []Top50Item
	Fallback       bool
	CandidateCount int
	Status         string
	Message        string
	Sources        []string
}

func clampScore(value, low, high float64) float64 {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}

func IndexScore(changePct *float64) float64 {
	if changePct == nil {
		return 50
	}
	return clampScore(50+*changePct*8, 0, 100)
}

func TurnoverScore(totalTurnover, baseline *float64) float64 {
	if totalTurnover == nil || *totalTurnover <= 0 {
		return 40
	}
	if baseline == nil || *baseline <= 0 {
		return clampScore(math.Min(100, 40+*totalTurnover/1e10), 0, 100)
	}
	ratio := *totalTurnover / *baseline
	return clampScore(30+math.Min(ratio, 2.5)*28, 0, 100)
}

func AdvanceDeclineScore(advance, decline int) float64 {
	total := advance + decline
	if total <= 0 {
		return 50
	}
	return clampScore(float64(advance)/float64(total)*100, 0, 100)
}

func ComputeHeatScore(weights map[string]float64, indexChange, totalTurnover *float64, advance, decline int, baseline *float64) float64 {
	parts := map[string]float64{
		"index":           IndexScore(indexChange),
		"turnover":        TurnoverScore(totalTurnover, baseline),
		"advance_decline": AdvanceDeclineScore(advance, decline),
	}
	score := 0.0
	for key, part := range parts {
		score += part * weights[key]
	}
	return math.Round(clampScore(score, 0, 100)*100) / 100
}

func HeatSummary(score float64, market string, indexChange *float64, advance, decline int) string {
	label := MarketMeta[market].Label
	trend := "震荡"
	if indexChange != nil {
		if *indexChange >= 1 {
			trend = "偏强"
		} else if *indexChange <= -1 {
			trend = "偏弱"
		}
	}
	breadth := "涨跌均衡"
	if float64(advance) > float64(decline)*1.2 {
		breadth = "普涨"
	} else if float64(decline) > float64(advance)*1.2 {
		breadth = "普跌"
	}
	level := "中性"
	if score >= activeHeatScore {
		level = "活跃"
	} else if score <= coldHeatScore {
		level = "偏冷"
	}
	idxText := "指数待更新"
	if indexChange != nil {
		idxText = fmt.Sprintf("指数%+.2f%%", *indexChange)
	}
	return fmt.Sprintf("%s%s，%s，%s（涨%d/跌%d），热度%s。", label, trend, idxText, breadth, advance, decline, level)
}

func FilterTop50(market string, candidates []Candidate) []Top50Item {
	meta := MarketMeta[market]
	filtered := make([]Candidate, 0, len(candidates))
	for _, item := range candidates {
		if item.Turnover == nil || *item.Turnover <= 0 {
			continue
		}
		if item.MarketCap == nil {
			continue
		}
		cap := *item.MarketCap
		if cap < meta.CapMin || cap > meta.CapMax {
			continue
		}
		filtered = append(filtered, item)
	}
	sort.Slice(filtered, func(i, j int) bool {
		return deref(filtered[i].Turnover) > deref(filtered[j].Turnover)
	})
	if len(filtered) > 50 {
		filtered = filtered[:50]
	}
	return ranked(filtered)
}

func FallbackTop50(market string, candidates []Candidate) []Top50Item {
	meta := MarketMeta[market]
	rankedAll := make([]Candidate, 0, len(candidates))
	for _, c := range candidates {
		if c.Turnover != nil && *c.Turnover > 0 {
			rankedAll = append(rankedAll, c)
		}
	}
	sort.Slice(rankedAll, func(i, j int) bool {
		return deref(rankedAll[i].Turnover) > deref(rankedAll[j].Turnover)
	})
	looseMin := meta.CapMin * 0.2
	looseMax := meta.CapMax * 5
	loose := []Candidate{}
	withCap := []Candidate{}
	for _, c := range rankedAll {
		if c.MarketCap == nil {
			continue
		}
		withCap = append(withCap, c)
		if *c.MarketCap >= looseMin && *c.MarketCap <= looseMax {
			loose = append(loose, c)
		}
	}
	pick := loose
	if len(pick) == 0 {
		pick = withCap
	}
	if len(pick) == 0 {
		pick = rankedAll
	}
	if len(pick) > 50 {
		pick = pick[:50]
	}
	return ranked(pick)
}

func CountBreadth(candidates []Candidate) (advance, decline, flat int) {
	for _, item := range candidates {
		if item.ChangePct == nil {
			continue
		}
		change := *item.ChangePct
		if change > breadthFlatBandPct {
			advance++
		} else if change < -breadthFlatBandPct {
			decline++
		} else {
			flat++
		}
	}
	return
}

func MergeCandidates(groups ...[]Candidate) []Candidate {
	bySymbol := map[string]Candidate{}
	for _, group := range groups {
		for _, item := range group {
			symbol := strings.TrimSpace(item.Symbol)
			if symbol == "" {
				continue
			}
			key := strings.ToUpper(symbol)
			current, ok := bySymbol[key]
			if !ok {
				cp := item
				cp.Symbol = symbol
				bySymbol[key] = cp
				continue
			}
			if emptyName(current.Name) && !emptyName(item.Name) {
				current.Name = item.Name
			}
			if current.MarketCap == nil && item.MarketCap != nil {
				current.MarketCap = item.MarketCap
			}
			if (current.Turnover == nil || *current.Turnover == 0) && item.Turnover != nil {
				current.Turnover = item.Turnover
			}
			if current.ChangePct == nil && item.ChangePct != nil {
				current.ChangePct = item.ChangePct
			}
			if current.Last == nil && item.Last != nil {
				current.Last = item.Last
			}
			if current.ChangeAmount == nil && item.ChangeAmount != nil {
				current.ChangeAmount = item.ChangeAmount
			}
			if current.TurnoverRate == nil && item.TurnoverRate != nil {
				current.TurnoverRate = item.TurnoverRate
			}
			if current.VolumeRatio == nil && item.VolumeRatio != nil {
				current.VolumeRatio = item.VolumeRatio
			}
			if current.Amplitude == nil && item.Amplitude != nil {
				current.Amplitude = item.Amplitude
			}
			if current.PE == nil && item.PE != nil {
				current.PE = item.PE
			}
			if current.MainNetInflow == nil && item.MainNetInflow != nil {
				current.MainNetInflow = item.MainNetInflow
			}
			if item.Turnover != nil && deref(current.Turnover) < *item.Turnover {
				current.Turnover = item.Turnover
			}
			bySymbol[key] = current
		}
	}
	out := make([]Candidate, 0, len(bySymbol))
	for _, v := range bySymbol {
		out = append(out, v)
	}
	return out
}

func BuildCollect(market, tradeDate string, weights map[string]float64, candidates []Candidate, extras Extras, baseline *float64) CollectResult {
	result := CollectResult{Market: market, TradeDate: tradeDate, Sources: extras.Source, CandidateCount: len(candidates)}
	if !IsWeekday(tradeDate) {
		result.Skipped = true
		result.Reason = "non_trading_day"
		return result
	}
	if len(candidates) == 0 {
		result.Skipped = true
		result.Reason = "public_eod_empty"
		return result
	}
	for i := range candidates {
		if candidates[i].Currency == "" {
			candidates[i].Currency = MarketMeta[market].Currency
		}
	}
	sampleAdv, sampleDec, sampleFlat := CountBreadth(candidates)
	advance, decline, flat := 0, 0, 0
	if extras.Advance != nil {
		advance = *extras.Advance
	}
	if extras.Decline != nil {
		decline = *extras.Decline
	}
	if extras.Flat != nil {
		flat = *extras.Flat
	}
	if advance+decline <= 0 {
		advance, decline, flat = sampleAdv, sampleDec, sampleFlat
	}
	total := 0.0
	hasTurnover := false
	for _, item := range candidates {
		if item.Turnover != nil {
			total += *item.Turnover
			hasTurnover = true
		}
	}
	if extras.IndexTurnover != nil {
		if !hasTurnover || *extras.IndexTurnover > total {
			total = *extras.IndexTurnover
			hasTurnover = true
		}
	}
	var totalPtr *float64
	if hasTurnover && total > 0 {
		v := total
		totalPtr = &v
	}
	top50 := FilterTop50(market, candidates)
	fallback := false
	if len(top50) == 0 {
		top50 = FallbackTop50(market, candidates)
		fallback = len(top50) > 0
	}
	if len(top50) == 0 {
		result.Skipped = true
		result.Reason = "cap_filter_empty"
		return result
	}
	score := ComputeHeatScore(weights, extras.IndexChange, totalPtr, advance, decline, baseline)
	result.HeatScore = score
	result.Summary = HeatSummary(score, market, extras.IndexChange, advance, decline)
	result.IndexChange = extras.IndexChange
	result.TotalTurnover = totalPtr
	result.Advance = advance
	result.Decline = decline
	result.Flat = flat
	result.Top50 = top50
	result.Fallback = fallback
	result.Status = "ok"
	result.Message = "public eod " + joinSources(extras.Source)
	if fallback {
		result.Message += " fallback"
	}
	return result
}

func ranked(items []Candidate) []Top50Item {
	out := make([]Top50Item, 0, len(items))
	for i, item := range items {
		name := item.Name
		if name == "" {
			name = item.Symbol
		}
		out = append(out, Top50Item{
			RankNo:        i + 1,
			Symbol:        item.Symbol,
			Name:          name,
			MarketCap:     item.MarketCap,
			Turnover:      item.Turnover,
			ChangePct:     item.ChangePct,
			Last:          item.Last,
			ChangeAmount:  item.ChangeAmount,
			TurnoverRate:  item.TurnoverRate,
			VolumeRatio:   item.VolumeRatio,
			Amplitude:     item.Amplitude,
			PE:            item.PE,
			MainNetInflow: item.MainNetInflow,
			Currency:      item.Currency,
		})
	}
	return out
}

func deref(v *float64) float64 {
	if v == nil {
		return 0
	}
	return *v
}

func emptyName(s string) bool { return strings.TrimSpace(s) == "" }

func joinSources(src []string) string {
	return strings.Join(src, ",")
}
