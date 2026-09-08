package market

import (
	"testing"
	"time"
)

func TestCombinePickScoreClosedMarket(t *testing.T) {
	factor := 70.0
	sent := -2.0
	got := CombinePickScore(&factor, &sent, nil, nil, false)
	if got < 60 || got > 65 {
		t.Fatalf("unexpected closed-market score: %v", got)
	}
}

func TestRecoFromSignalBuy(t *testing.T) {
	reco, stance := RecoFromSignal("BUY", 65)
	if reco != "买入" || stance != "偏多" {
		t.Fatalf("expected buy reco, got %s %s", reco, stance)
	}
}

func TestMergeCandidatesSkipsIndex(t *testing.T) {
	out := MergeCandidates(
		[]Candidate{{Symbol: "^GSPC", Name: "S&P", Market: "US", Category: "index"}},
		[]Candidate{{Symbol: "AAPL", Name: "Apple", Market: "US", Category: "mag7"}},
		10,
	)
	if len(out) != 1 || out[0].Symbol != "AAPL" {
		t.Fatalf("expected only AAPL, got %+v", out)
	}
}

func TestIsInSessionWeekend(t *testing.T) {
	sat, _ := time.Parse("2006-01-02 15:04:05", "2026-09-05 10:00:00")
	if IsInSession("US", sat) {
		t.Fatal("US should be closed on Saturday")
	}
}
