package heat

import (
	"math"
	"strings"
	"testing"
	"time"
)

func f64(v float64) *float64 { return &v }

func TestFilterTop50US(t *testing.T) {
	candidates := []Candidate{
		{Symbol: "A", Name: "A", MarketCap: f64(5e8), Turnover: f64(1e9), ChangePct: f64(1), Last: f64(10), Currency: "USD"},
		{Symbol: "B", Name: "B", MarketCap: f64(5e9), Turnover: f64(2e9), ChangePct: f64(-1), Last: f64(20), Currency: "USD"},
		{Symbol: "C", Name: "C", MarketCap: f64(50e9), Turnover: f64(3e9), ChangePct: f64(2), Last: f64(30), Currency: "USD"},
		{Symbol: "D", Name: "D", MarketCap: f64(200e9), Turnover: f64(9e9), ChangePct: f64(0.5), Last: f64(40), Currency: "USD"},
	}
	top := FilterTop50("US", candidates)
	if len(top) != 2 || top[0].Symbol != "C" || top[1].Symbol != "B" {
		t.Fatalf("symbols=%v", top)
	}
	if top[0].RankNo != 1 || top[0].Last == nil || *top[0].Last != 30 {
		t.Fatalf("rank/last %+v", top[0])
	}
}

func TestFilterTop50CN(t *testing.T) {
	candidates := []Candidate{
		{Symbol: "600519", Name: "茅台", MarketCap: f64(15e9), Turnover: f64(8e9), ChangePct: f64(1), Currency: "CNY"},
		{Symbol: "000001", Name: "平安", MarketCap: f64(250e9), Turnover: f64(9e9), ChangePct: f64(-0.5), Currency: "CNY"},
	}
	top := FilterTop50("CN", candidates)
	if len(top) != 1 || top[0].Symbol != "600519" {
		t.Fatalf("top=%+v", top)
	}
}

func TestComputeHeatScoreWeighted(t *testing.T) {
	weights := map[string]float64{"index": 0.4, "turnover": 0.3, "advance_decline": 0.3}
	score := ComputeHeatScore(weights, f64(2.0), f64(1e10), 120, 80, f64(8e9))
	if score < 0 || score > 100 {
		t.Fatalf("score=%v", score)
	}
	if math.Abs(score-63.9) > 0.01 {
		t.Fatalf("expected 63.9 got %v", score)
	}
}

func TestBuildCollectSkipsWeekend(t *testing.T) {
	res := BuildCollect("US", "2026-09-06", DefaultWeights(), []Candidate{{Symbol: "AAPL", Turnover: f64(1), MarketCap: f64(5e9)}}, Extras{}, nil)
	if !res.Skipped || res.Reason != "non_trading_day" {
		t.Fatalf("%+v", res)
	}
}

func TestBuildCollectSkipsEmpty(t *testing.T) {
	res := BuildCollect("US", "2026-09-08", DefaultWeights(), nil, Extras{}, nil)
	if !res.Skipped || res.Reason != "public_eod_empty" {
		t.Fatalf("%+v", res)
	}
}

func TestBuildCollectUsesFallbackWhenCapEmpty(t *testing.T) {
	candidates := []Candidate{
		{Symbol: "MEGA", Name: "Mega", MarketCap: f64(500e9), Turnover: f64(9e9), ChangePct: f64(1), Last: f64(100), Currency: "USD"},
	}
	res := BuildCollect("US", "2026-09-08", NormalizeWeights(DefaultWeights()), candidates, Extras{Source: []string{"sina-us"}}, nil)
	if res.Skipped {
		t.Fatalf("skipped %+v", res)
	}
	if !res.Fallback || len(res.Top50) != 1 || res.Top50[0].Symbol != "MEGA" {
		t.Fatalf("fallback %+v", res)
	}
	if res.Status != "ok" {
		t.Fatalf("status=%s", res.Status)
	}
}

func TestResolveTradeDateUsesMarketTZ(t *testing.T) {
	// 2026-09-08 02:30 UTC is still 2026-09-07 in New York.
	now := time.Date(2026, 9, 8, 2, 30, 0, 0, time.UTC)
	got := ResolveTradeDate("US", "", now)
	if got != "2026-09-07" {
		t.Fatalf("tradeDate=%s", got)
	}
	if ResolveTradeDate("US", "2026-09-01 extra", now) != "2026-09-01" {
		t.Fatal("explicit trade date not honored")
	}
}

func TestMergeCandidatesFillsExtras(t *testing.T) {
	out := MergeCandidates(
		[]Candidate{{Symbol: "AAA", Turnover: f64(1), ChangePct: f64(1)}},
		[]Candidate{{
			Symbol: "aaa", ChangeAmount: f64(0.5), TurnoverRate: f64(1.2),
			VolumeRatio: f64(1.5), Amplitude: f64(3), PE: f64(18), MainNetInflow: f64(1e7),
		}},
	)
	if len(out) != 1 {
		t.Fatalf("len=%d", len(out))
	}
	got := out[0]
	if got.ChangeAmount == nil || *got.ChangeAmount != 0.5 || got.PE == nil || *got.PE != 18 {
		t.Fatalf("%+v", got)
	}
	if got.TurnoverRate == nil || got.VolumeRatio == nil || got.Amplitude == nil || got.MainNetInflow == nil {
		t.Fatalf("extras %+v", got)
	}
}

func TestFilterTop50KeepsExtras(t *testing.T) {
	top := FilterTop50("US", []Candidate{{
		Symbol: "C", Name: "C", MarketCap: f64(50e9), Turnover: f64(3e9),
		ChangePct: f64(2), Last: f64(30), ChangeAmount: f64(0.6), TurnoverRate: f64(1.1),
		VolumeRatio: f64(1.4), Amplitude: f64(2.2), PE: f64(25), MainNetInflow: f64(8e6),
		Currency: "USD",
	}})
	if len(top) != 1 {
		t.Fatalf("len=%d", len(top))
	}
	if top[0].ChangeAmount == nil || top[0].PE == nil || top[0].MainNetInflow == nil {
		t.Fatalf("extras dropped %+v", top[0])
	}
}

func TestHeatSummary(t *testing.T) {
	text := HeatSummary(80, "US", f64(1.5), 120, 40)
	if text == "" || !strings.Contains(text, "美股偏强") || !strings.Contains(text, "普涨") || !strings.Contains(text, "活跃") {
		t.Fatalf("summary=%s", text)
	}
}
