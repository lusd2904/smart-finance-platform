package factor

import "testing"

func trendingBars(n int) []Bar {
	price := 100.0
	out := make([]Bar, n)
	for i := 0; i < n; i++ {
		if i%3 == 0 {
			price -= 0.2
		} else {
			price += 0.5
		}
		out[i] = Bar{
			Date:   "2024-01-02",
			Open:   price - 0.3,
			High:   price + 0.6,
			Low:    price - 0.7,
			Close:  price,
			Volume: 1_000_000 + float64(i)*1000,
		}
	}
	return out
}

func TestComputeMetricsNeeds20Bars(t *testing.T) {
	m := ComputeMetrics(trendingBars(10))
	if m.OK {
		t.Fatal("expected insufficient history")
	}
}

func TestComputeFromKlinesScoresAndAlphas(t *testing.T) {
	res := ComputeFromKlines(trendingBars(80), "balanced", nil)
	if !res.OK {
		t.Fatalf("compute failed: %s", res.Reason)
	}
	if res.Score.Total < 0 || res.Score.Total > 100 {
		t.Fatalf("total out of range: %v", res.Score.Total)
	}
	if res.Score.FactorVersion != SchemaVersion {
		t.Fatalf("version %s", res.Score.FactorVersion)
	}
	if res.Metrics.Alpha101N == 0 || res.Metrics.Alpha158N == 0 {
		t.Fatalf("expected alpha counts 101=%d 158=%d", res.Metrics.Alpha101N, res.Metrics.Alpha158N)
	}
	if _, ok := res.Metrics.Alpha101["alpha006"]; !ok {
		t.Fatal("missing alpha006")
	}
	if _, ok := res.Metrics.Alpha101["alpha012"]; !ok {
		t.Fatal("missing alpha012")
	}
	if _, ok := res.Metrics.Alpha158["KMID"]; !ok {
		t.Fatal("missing KMID")
	}
}

func TestDecideSignalThresholds(t *testing.T) {
	buy := DecideSignal(Score{Total: 80, RiskLevel: "low", TrendDirection: "up", Tags: []string{"强势"}}, "balanced", nil)
	if buy.Signal != "BUY" {
		t.Fatalf("buy got %s", buy.Signal)
	}
	sell := DecideSignal(Score{Total: 20, RiskLevel: "high", TrendDirection: "down"}, "balanced", nil)
	if sell.Signal != "SELL" {
		t.Fatalf("sell got %s", sell.Signal)
	}
	hold := DecideSignal(Score{Total: 50, RiskLevel: "low", TrendDirection: "sideways"}, "balanced", nil)
	if hold.Signal != "HOLD" {
		t.Fatalf("hold got %s", hold.Signal)
	}
}

func TestMergeProfileWeights(t *testing.T) {
	w := MergeProfileConfig("balanced", map[string]any{
		"weights": map[string]any{"trend": 0.5, "volume": 0.2},
	})
	if w["trend"] != 0.5 {
		t.Fatalf("trend weight %v", w["trend"])
	}
	if w["volumeFlow"] != 0.2 {
		t.Fatalf("volume alias %v", w["volumeFlow"])
	}
}

func TestCrossSectionRanks(t *testing.T) {
	rows := []CSRow{
		{Symbol: "A", Return20: 1, RSI14: 10, VolumeRatio20: 1, DistanceHigh20: -1, Alpha101: map[string]float64{"alpha006": 0.1}},
		{Symbol: "B", Return20: 2, RSI14: 20, VolumeRatio20: 2, DistanceHigh20: 0, Alpha101: map[string]float64{"alpha006": 0.2}},
		{Symbol: "C", Return20: 3, RSI14: 30, VolumeRatio20: 3, DistanceHigh20: 1, Alpha101: map[string]float64{"alpha006": 0.3}},
	}
	AttachCrossSection(rows)
	if rows[2].AlphaCs["csMom20"] != 1 {
		t.Fatalf("top mom rank %v", rows[2].AlphaCs["csMom20"])
	}
	if rows[0].AlphaCsCount == 0 {
		t.Fatal("expected cs counts")
	}
}

func TestScanUniverseSkipsIndex(t *testing.T) {
	u := ScanUniverse()
	for _, inst := range u {
		if inst.Category == "index" || (len(inst.Symbol) > 0 && inst.Symbol[0] == '^') {
			t.Fatalf("index leaked: %+v", inst)
		}
	}
	if len(u) < 50 {
		t.Fatalf("universe too small: %d", len(u))
	}
}
