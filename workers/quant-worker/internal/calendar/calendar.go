// Package calendar ports A-share session helpers from utils/trading_calendar.py.
package calendar

import "time"

var cnLocation = mustLoad("Asia/Shanghai")

// CN holidays 2025–2027 (State Council; makeup workdays are not listed here).
var cnHolidays = map[string]struct{}{
	"2025-01-01": {}, "2025-01-28": {}, "2025-01-29": {}, "2025-01-30": {},
	"2025-01-31": {}, "2025-02-01": {}, "2025-02-02": {}, "2025-02-03": {},
	"2025-02-04": {}, "2025-04-04": {}, "2025-04-05": {}, "2025-04-06": {},
	"2025-05-01": {}, "2025-05-02": {}, "2025-05-03": {}, "2025-05-04": {},
	"2025-05-05": {}, "2025-05-31": {}, "2025-06-01": {}, "2025-06-02": {},
	"2025-10-01": {}, "2025-10-02": {}, "2025-10-03": {}, "2025-10-04": {},
	"2025-10-05": {}, "2025-10-06": {}, "2025-10-07": {}, "2025-10-08": {},
	"2026-01-01": {}, "2026-01-02": {}, "2026-02-15": {}, "2026-02-16": {},
	"2026-02-17": {}, "2026-02-18": {}, "2026-02-19": {}, "2026-02-20": {},
	"2026-02-21": {}, "2026-02-22": {}, "2026-02-23": {}, "2026-04-04": {},
	"2026-04-05": {}, "2026-04-06": {}, "2026-05-01": {}, "2026-05-02": {},
	"2026-05-03": {}, "2026-05-04": {}, "2026-05-05": {}, "2026-06-19": {},
	"2026-06-20": {}, "2026-06-21": {}, "2026-10-01": {}, "2026-10-02": {},
	"2026-10-03": {}, "2026-10-04": {}, "2026-10-05": {}, "2026-10-06": {},
	"2026-10-07": {}, "2026-10-08": {}, "2027-01-01": {},
}

var cnMakeup = map[string]struct{}{
	"2025-01-26": {}, "2025-02-08": {}, "2025-04-27": {}, "2025-09-28": {},
	"2025-10-11": {}, "2026-02-14": {}, "2026-02-28": {}, "2026-09-27": {},
	"2026-10-10": {},
}

func mustLoad(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		return time.FixedZone("CST", 8*3600)
	}
	return loc
}

func TodayCN(now time.Time) time.Time {
	if now.IsZero() {
		now = time.Now()
	}
	t := now.In(cnLocation)
	return time.Date(t.Year(), t.Month(), t.Day(), 0, 0, 0, 0, cnLocation)
}

func key(day time.Time) string {
	return day.In(cnLocation).Format("2006-01-02")
}

func IsWeekday(day time.Time) bool {
	w := day.Weekday()
	return w != time.Saturday && w != time.Sunday
}

func IsCNTradingDay(day time.Time) bool {
	if day.IsZero() {
		day = TodayCN(time.Now())
	}
	if _, ok := cnHolidays[key(day)]; ok {
		return false
	}
	if _, ok := cnMakeup[key(day)]; ok {
		return true
	}
	return IsWeekday(day)
}

func NextCNTradingDay(day time.Time) time.Time {
	if day.IsZero() {
		day = TodayCN(time.Now())
	}
	cursor := day.AddDate(0, 0, 1)
	for i := 0; i < 20; i++ {
		if IsCNTradingDay(cursor) {
			return time.Date(cursor.Year(), cursor.Month(), cursor.Day(), 0, 0, 0, 0, cnLocation)
		}
		cursor = cursor.AddDate(0, 0, 1)
	}
	return cursor
}

func FormatDate(day time.Time) string {
	return day.In(cnLocation).Format("2006-01-02")
}
