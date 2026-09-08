package calendar

import (
	"testing"
	"time"
)

func TestCNTradingDayWeekendAndHoliday(t *testing.T) {
	sat := time.Date(2026, 9, 5, 12, 0, 0, 0, cnLocation) // Saturday
	if IsCNTradingDay(sat) {
		t.Fatal("Saturday should not be a CN trading day")
	}
	national := time.Date(2026, 10, 1, 12, 0, 0, 0, cnLocation)
	if IsCNTradingDay(national) {
		t.Fatal("National Day should be a holiday")
	}
	makeup := time.Date(2026, 10, 10, 12, 0, 0, 0, cnLocation) // Saturday makeup
	if !IsCNTradingDay(makeup) {
		t.Fatal("makeup Saturday should trade")
	}
	weekday := time.Date(2026, 9, 8, 12, 0, 0, 0, cnLocation) // Tuesday
	if !IsCNTradingDay(weekday) {
		t.Fatal("Tuesday should trade")
	}
}

func TestNextCNTradingDaySkipsWeekend(t *testing.T) {
	friday := time.Date(2026, 9, 4, 0, 0, 0, 0, cnLocation)
	next := NextCNTradingDay(friday)
	if FormatDate(next) != "2026-09-07" {
		t.Fatalf("next trading day after Friday = %s", FormatDate(next))
	}
}
