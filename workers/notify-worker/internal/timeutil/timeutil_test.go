package timeutil

import (
	"testing"
	"time"
)

func TestShanghaiLocationNeverNil(t *testing.T) {
	if Shanghai == nil {
		t.Fatal("Shanghai location must not be nil")
	}
	// Must not panic when converting wall-clock instants.
	_ = time.Now().In(Shanghai)
}

func TestLocationForNeverNil(t *testing.T) {
	cases := []string{"", "Asia/Shanghai", "Invalid/Timezone"}
	for _, name := range cases {
		loc := LocationFor(name)
		if loc == nil {
			t.Fatalf("LocationFor(%q) returned nil", name)
		}
		_ = time.Now().In(loc)
	}
}

func TestIsCNTradingDay(t *testing.T) {
	// Thursday 10:00 CST = Thursday 02:00 UTC
	thu := time.Date(2026, 9, 3, 2, 0, 0, 0, time.UTC)
	if !IsCNTradingDay(thu) {
		t.Fatal("Thursday in Shanghai should be a trading day")
	}

	// Saturday 10:00 CST = Saturday 02:00 UTC
	sat := time.Date(2026, 9, 5, 2, 0, 0, 0, time.UTC)
	if IsCNTradingDay(sat) {
		t.Fatal("Saturday in Shanghai should not be a trading day")
	}

	// Sunday 10:00 CST = Sunday 02:00 UTC
	sun := time.Date(2026, 9, 6, 2, 0, 0, 0, time.UTC)
	if IsCNTradingDay(sun) {
		t.Fatal("Sunday in Shanghai should not be a trading day")
	}

	// Friday 16:00 UTC = Saturday 00:00 CST (weekend boundary)
	friUTC := time.Date(2026, 9, 4, 16, 0, 0, 0, time.UTC)
	if IsCNTradingDay(friUTC) {
		t.Fatal("Saturday 00:00 CST should not be a trading day")
	}
}

func TestIsCNTradingDayUsesEmbeddedZoneinfo(t *testing.T) {
	loc, err := time.LoadLocation(ShanghaiTZ)
	if err != nil {
		t.Fatalf("embedded tzdata should provide %s: %v", ShanghaiTZ, err)
	}
	mon := time.Date(2026, 9, 7, 12, 0, 0, 0, loc)
	if !IsCNTradingDay(mon) {
		t.Fatal("Monday in Shanghai should be a trading day")
	}
}

func TestLoadLocationFallbackNeverPanics(t *testing.T) {
	loc := loadLocation("No/Such/Zone", "CST", 8*3600)
	if loc == nil {
		t.Fatal("fallback location must not be nil")
	}
	wd := time.Date(2026, 9, 7, 12, 0, 0, 0, time.UTC).In(loc).Weekday()
	if wd != time.Monday {
		t.Fatalf("expected Monday in CST+8, got %v", wd)
	}
}
