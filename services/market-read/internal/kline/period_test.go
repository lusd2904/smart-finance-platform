package kline

import "testing"

func TestNormalizePeriod(t *testing.T) {
	if NormalizePeriod("1m") != "1min" {
		t.Fatalf("expected 1min")
	}
	if NormalizePeriod("周k") != "weekly" {
		t.Fatalf("expected weekly")
	}
}

func TestDefaultLimitCaps(t *testing.T) {
	n := 9000
	lim := DefaultLimit("daily", &n)
	if lim == nil || *lim != 5000 {
		t.Fatalf("expected cap 5000, got %v", lim)
	}
}

func TestResampleMinuteBars(t *testing.T) {
	o, h, l, c, v := 1.0, 2.0, 0.5, 1.5, 10.0
	bars := []Bar{{
		Date: "2026-09-05 09:31", Open: &o, High: &h, Low: &l, Close: &c, Volume: &v,
	}}
	out := ResampleMinuteBars(bars, "5min")
	if len(out) != 1 {
		t.Fatalf("expected 1 bar, got %d", len(out))
	}
}
