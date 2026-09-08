package factorqc

import (
	"fmt"
	"testing"
)

func trendingPanel(nDates, nSymbols int) Panel {
	dates := make([]string, nDates)
	symbols := make([]string, nSymbols)
	closeM := make([][]float64, nDates)
	volM := make([][]float64, nDates)
	for i := 0; i < nDates; i++ {
		dates[i] = fmt.Sprintf("2023-01-%02d", i+1)
		if i >= 31 {
			dates[i] = fmt.Sprintf("2023-02-%02d", i-30)
		}
		if i >= 59 {
			dates[i] = fmt.Sprintf("2023-03-%02d", i-58)
		}
		closeM[i] = make([]float64, nSymbols)
		volM[i] = make([]float64, nSymbols)
		for j := 0; j < nSymbols; j++ {
			if i == 0 {
				closeM[i][j] = 100
			} else {
				drift := 0.001 + float64(j)*0.0008
				noise := float64((i*(j+3))%7-3) * 0.0005
				closeM[i][j] = closeM[i-1][j] * (1 + drift + noise)
			}
			volM[i][j] = 1_000_000
			if j == 0 && i == 0 {
				symbols[j] = fmt.Sprintf("S%02d", j)
			}
		}
	}
	for j := 0; j < nSymbols; j++ {
		symbols[j] = fmt.Sprintf("S%02d", j)
	}
	// fix dates to be sortable unique
	for i := 0; i < nDates; i++ {
		dates[i] = fmt.Sprintf("2023-%03d", i+1)
	}
	return Panel{Dates: dates, Symbols: symbols, Close: closeM, Volume: volM}
}

func TestKlinesToPanelAlignsDates(t *testing.T) {
	p := KlinesToPanel(map[string][]struct {
		Date   string
		Close  float64
		Volume float64
	}{
		"AAA": {{"2024-01-02", 10, 100}, {"2024-01-03", 11, 110}},
		"BBB": {{"2024-01-03", 20, 200}, {"2024-01-04", 21, 210}},
	})
	if len(p.Symbols) != 2 || p.Symbols[0] != "AAA" {
		t.Fatalf("symbols %v", p.Symbols)
	}
	// date 2024-01-03 is index 1
	if p.Close[1][0] != 11 {
		t.Fatalf("AAA on 01-03 = %v", p.Close[1][0])
	}
	if !isNaN(p.Close[0][1]) {
		t.Fatalf("BBB on 01-02 should be missing")
	}
	if p.Volume[1][1] != 200 {
		t.Fatalf("BBB volume %v", p.Volume[1][1])
	}
}

func isNaN(v float64) bool { return v != v }

func TestMomentumICPositiveOnTrendingPanel(t *testing.T) {
	p := trendingPanel(80, 20)
	mom20 := pctChange(p.Close, 20)
	rows := EvaluateFactor(mom20, p.Close, []int{1, 5})
	var h1 *HorizonRow
	for i := range rows {
		if rows[i].Horizon == 1 {
			h1 = &rows[i]
		}
	}
	if h1 == nil {
		t.Fatal("missing horizon 1")
	}
	if h1.SampleDates < 20 {
		t.Fatalf("sampleDates %d", h1.SampleDates)
	}
	if h1.ICMean == nil || *h1.ICMean <= 0.3 {
		t.Fatalf("icMean %v", h1.ICMean)
	}
	if h1.IR == nil || *h1.IR <= 0 {
		t.Fatalf("ir %v", h1.IR)
	}
	if len(h1.Quantiles) == 0 {
		t.Fatal("expected quantiles")
	}
	if h1.Spread == nil || *h1.Spread <= 0 {
		t.Fatalf("spread %v", h1.Spread)
	}
}

func TestComputeReportRejectsSmallCrossSection(t *testing.T) {
	p := trendingPanel(10, 3)
	rep := ComputeReport(p, "US")
	if rep.OK {
		t.Fatal("expected insufficient universe")
	}
}
