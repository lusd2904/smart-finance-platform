package store

import (
	"testing"
	"time"
)

func TestBeijingLocationNeverNil(t *testing.T) {
	loc := beijingLocation()
	if loc == nil {
		t.Fatal("beijingLocation must not be nil")
	}
	_ = time.Now().In(loc)
}

func TestBeijingNowNeverPanics(t *testing.T) {
	got := beijingNow()
	if got == "" {
		t.Fatal("beijingNow returned empty string")
	}
	if _, err := time.Parse("2006-01-02 15:04:05", got); err != nil {
		t.Fatalf("beijingNow format: %v", err)
	}
}

func TestLoadLocationOrCSTFallbackNeverPanics(t *testing.T) {
	loc := loadLocationOrCST("No/Such/Zone")
	if loc == nil {
		t.Fatal("fallback location must not be nil")
	}
	// 12:00 UTC is 20:00 CST+8 — must not panic and must apply +8.
	converted := time.Date(2026, 9, 7, 12, 0, 0, 0, time.UTC).In(loc)
	if converted.Hour() != 20 {
		t.Fatalf("expected 20:00 CST+8, got %s", converted.Format("15:04"))
	}
}
