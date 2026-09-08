package indicators

import "testing"

func TestLatestSnapshot(t *testing.T) {
	bars := []Bar{{Close: 10}, {Close: 11}, {Close: 12}, {Close: 13}, {Close: 14}, {Close: 15}, {Close: 16}, {Close: 17}, {Close: 18}, {Close: 19}, {Close: 20}, {Close: 21}, {Close: 22}, {Close: 23}, {Close: 24}}
	dates := []string{"d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "d10", "d11", "d12", "d13", "d14", "d15"}
	snap := LatestSnapshot(bars, dates)
	if !snap.Has {
		t.Fatal("expected snapshot")
	}
	if snap.Close != 24 {
		t.Fatalf("close=%v", snap.Close)
	}
}

func TestTechScore(t *testing.T) {
	if TechScore(50, 1) <= TechScore(50, -1) {
		t.Fatal("macd>0 should score higher")
	}
}
