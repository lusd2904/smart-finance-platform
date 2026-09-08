package tradeexec

import (
	"testing"
	"time"
)

func TestCNTradingDay(t *testing.T) {
	nyd := time.Date(2026, 1, 1, 12, 0, 0, 0, cnLocation)
	if IsCNTradingDay(nyd) {
		t.Fatal("2026-01-01 is a holiday")
	}
	makeup := time.Date(2026, 2, 14, 12, 0, 0, 0, cnLocation)
	if !IsCNTradingDay(makeup) {
		t.Fatal("2026-02-14 is a makeup Saturday")
	}
	sat := time.Date(2026, 9, 5, 12, 0, 0, 0, cnLocation) // Saturday
	if IsCNTradingDay(sat) {
		t.Fatal("weekend")
	}
	next := NextCNTradingDay(time.Date(2026, 1, 1, 0, 0, 0, 0, cnLocation))
	if dateKey(next) != "2026-01-05" { // Fri 2 Jan holiday, Sat/Sun, Mon 5
		// 2026-01-01 Thu holiday, 01-02 Fri holiday, 01-03 Sat, 01-04 Sun → 01-05
		if dateKey(next) != "2026-01-05" {
			t.Fatalf("next=%s", dateKey(next))
		}
	}
}

func TestUSOutsideRTHMode(t *testing.T) {
	// Tuesday 10:00 ET → anytime
	et := time.Date(2026, 9, 8, 10, 0, 0, 0, usLocation)
	if USOutsideRTHMode(et) != "anytime" {
		t.Fatal(USOutsideRTHMode(et))
	}
	// Tuesday 21:00 ET → overnight
	et = time.Date(2026, 9, 8, 21, 0, 0, 0, usLocation)
	if USOutsideRTHMode(et) != "overnight" {
		t.Fatal(USOutsideRTHMode(et))
	}
}

func TestIsMarketSessionOpenUS(t *testing.T) {
	// Tuesday 10:00 ET regular
	et := time.Date(2026, 9, 8, 10, 0, 0, 0, usLocation)
	if !IsMarketSessionOpen("US", et) {
		t.Fatal("regular should be open")
	}
	// Saturday noon ET
	sat := time.Date(2026, 9, 5, 12, 0, 0, 0, usLocation)
	if IsMarketSessionOpen("US", sat) {
		t.Fatal("saturday closed")
	}
}
