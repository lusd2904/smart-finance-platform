package indicators

import "math"

type Bar struct {
	Close float64
	High  float64
	Low   float64
}

type Snapshot struct {
	Date  string
	Close float64
	RSI12 float64
	MACD  float64
	Has   bool
}

func LatestSnapshot(bars []Bar, dates []string) Snapshot {
	if len(bars) == 0 {
		return Snapshot{}
	}
	closes := make([]float64, len(bars))
	for i, b := range bars {
		closes[i] = b.Close
	}
	rsi := rsiSeries(closes, 12)
	macd := macdSeries(closes)
	date := ""
	if len(dates) > 0 {
		date = dates[len(dates)-1]
	}
	snap := Snapshot{
		Date:  date,
		Close: closes[len(closes)-1],
		Has:   true,
	}
	if len(rsi) > 0 {
		snap.RSI12 = rsi[len(rsi)-1]
	}
	if len(macd) > 0 {
		snap.MACD = macd[len(macd)-1]
	}
	return snap
}

func rsiSeries(closes []float64, length int) []float64 {
	if len(closes) < length+1 || length <= 0 {
		return nil
	}
	out := make([]float64, len(closes))
	var avgGain, avgLoss float64
	for i := 1; i <= length; i++ {
		delta := closes[i] - closes[i-1]
		if delta > 0 {
			avgGain += delta
		} else {
			avgLoss -= delta
		}
	}
	avgGain /= float64(length)
	avgLoss /= float64(length)
	out[length] = calcRSI(avgGain, avgLoss)
	for i := length + 1; i < len(closes); i++ {
		delta := closes[i] - closes[i-1]
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

func macdSeries(closes []float64) []float64 {
	if len(closes) < 26 {
		return nil
	}
	ema12 := ema(closes, 12)
	ema26 := ema(closes, 26)
	out := make([]float64, len(closes))
	for i := range closes {
		if i >= 25 {
			out[i] = ema12[i] - ema26[i]
		}
	}
	return out
}

func ema(values []float64, length int) []float64 {
	out := make([]float64, len(values))
	if len(values) == 0 || length <= 0 {
		return out
	}
	k := 2.0 / (float64(length) + 1)
	out[0] = values[0]
	for i := 1; i < len(values); i++ {
		out[i] = values[i]*k + out[i-1]*(1-k)
	}
	return out
}

func TechScore(rsi, macd float64) float64 {
	score := 50.0
	score += (rsi - 50) * 0.4
	if macd > 0 {
		score += 8
	} else if macd < 0 {
		score -= 8
	}
	if score < 0 {
		return 0
	}
	if score > 100 {
		return 100
	}
	return math.Round(score*10) / 10
}
