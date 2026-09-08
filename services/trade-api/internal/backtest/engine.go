package backtest

import (
	"math"
	"strings"
)

const (
	Lookback    = 30
	DefaultFee  = 0.0005
	DefaultSlip = 0.0002
)

type Kline struct {
	Date  string
	Close float64
}

type EquityPoint struct {
	Date   string  `json:"date"`
	Equity float64 `json:"equity"`
	Signal string  `json:"signal"`
}

type SimResult struct {
	OK           bool          `json:"ok"`
	Trades       int           `json:"trades"`
	RoundTrips   int           `json:"roundTrips"`
	ReturnPct    float64       `json:"returnPct"`
	FinalEquity  float64       `json:"finalEquity"`
	MaxDrawdown  float64       `json:"maxDrawdown"`
	WinRate      float64       `json:"winRate"`
	Equity       []EquityPoint `json:"equity"`
}

func SimulateLongOnly(klines []Kline, signals []string, initialCapital, feeRate, slippage float64) SimResult {
	if initialCapital <= 0 {
		initialCapital = 100000
	}
	if feeRate <= 0 {
		feeRate = DefaultFee
	}
	if slippage <= 0 {
		slippage = DefaultSlip
	}
	n := len(klines)
	if len(signals) < n {
		n = len(signals)
	}
	cash := initialCapital
	pos := 0.0
	trades := 0
	roundTrips := 0
	winning := 0
	lastBuy := 0.0
	peak := initialCapital
	maxDD := 0.0
	equityCurve := make([]EquityPoint, 0, n)
	lastClose := 0.0

	for i := 0; i < n; i++ {
		price := klines[i].Close
		if price <= 0 {
			continue
		}
		lastClose = price
		sig := strings.ToUpper(strings.TrimSpace(signals[i]))
		if sig == "" {
			sig = "HOLD"
		}
		if sig == "BUY" && pos <= 0 && cash > 0 {
			execPrice := price * (1 + slippage)
			cost := execPrice * (1 + feeRate)
			pos = cash / cost
			lastBuy = execPrice
			cash = 0
			trades++
		} else if sig == "SELL" && pos > 0 {
			execPrice := price * (1 - slippage)
			cash = pos * execPrice * (1 - feeRate)
			roundTrips++
			if execPrice > lastBuy {
				winning++
			}
			pos = 0
			trades++
		}
		equity := cash + pos*price
		if equity > peak {
			peak = equity
		}
		if peak > 0 {
			dd := (peak - equity) / peak
			if dd > maxDD {
				maxDD = dd
			}
		}
		equityCurve = append(equityCurve, EquityPoint{
			Date: klines[i].Date, Equity: round2(equity), Signal: sig,
		})
	}
	finalEquity := cash + pos*lastClose
	winRate := 0.0
	if roundTrips > 0 {
		winRate = round2(float64(winning) / float64(roundTrips) * 100)
	}
	returnPct := 0.0
	if initialCapital > 0 {
		returnPct = round2((finalEquity/initialCapital - 1) * 100)
	}
	return SimResult{
		OK: true, Trades: trades, RoundTrips: roundTrips,
		ReturnPct: returnPct, FinalEquity: round2(finalEquity),
		MaxDrawdown: round2(maxDD * 100), WinRate: winRate, Equity: equityCurve,
	}
}

func FactorSignals(klines []Kline, profile string, weights map[string]float64) []string {
	out := make([]string, len(klines))
	start := Lookback
	if start < 20 {
		start = 20
	}
	buyThr, sellThr := profileThresholds(profile, weights)
	for i := range out {
		out[i] = "HOLD"
	}
	for i := start; i < len(klines); i++ {
		score := scoreWindow(klines[:i+1], profile)
		if score >= buyThr {
			out[i] = "BUY"
		} else if score <= sellThr {
			out[i] = "SELL"
		}
	}
	return out
}

func profileThresholds(profile string, weights map[string]float64) (buy float64, sell float64) {
	switch strings.ToLower(profile) {
	case "conservative":
		return 72, 42
	case "aggressive":
		return 56, 32
	default:
		return 64, 38
	}
}

func scoreWindow(klines []Kline, profile string) float64 {
	n := len(klines)
	if n < 20 {
		return 50
	}
	closes := make([]float64, n)
	for i, k := range klines {
		closes[i] = k.Close
	}
	last := closes[n-1]
	ma5 := sma(closes, 5)
	ma20 := sma(closes, 20)
	momentum := 0.0
	if n > 10 && closes[n-11] > 0 {
		momentum = (last/closes[n-11] - 1) * 100
	}
	trend := 50.0
	if ma20 > 0 {
		trend = clamp(50 + (ma5-ma20)/ma20*500, 0, 100)
	}
	momScore := clamp(50+momentum*5, 0, 100)
	wTrend, wMom := 0.55, 0.45
	switch strings.ToLower(profile) {
	case "conservative":
		wTrend, wMom = 0.65, 0.35
	case "aggressive":
		wTrend, wMom = 0.45, 0.55
	}
	return trend*wTrend + momScore*wMom
}

func sma(values []float64, period int) float64 {
	if len(values) < period || period <= 0 {
		return 0
	}
	sum := 0.0
	for i := len(values) - period; i < len(values); i++ {
		sum += values[i]
	}
	return sum / float64(period)
}

func clamp(v, lo, hi float64) float64 {
	return math.Max(lo, math.Min(hi, v))
}

func round2(v float64) float64 {
	return math.Round(v*100) / 100
}
