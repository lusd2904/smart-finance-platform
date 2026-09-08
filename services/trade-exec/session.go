package tradeexec

import (
	"time"
)

var cnLocation = mustLoad("Asia/Shanghai")
var hkLocation = mustLoad("Asia/Hong_Kong")
var usLocation = mustLoad("America/New_York")

func mustLoad(name string) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		return time.UTC
	}
	return loc
}

var cnHolidays = map[string]struct{}{
	"2025-01-01": {}, "2025-01-28": {}, "2025-01-29": {}, "2025-01-30": {},
	"2025-01-31": {}, "2025-02-01": {}, "2025-02-02": {}, "2025-02-03": {}, "2025-02-04": {},
	"2025-04-04": {}, "2025-04-05": {}, "2025-04-06": {},
	"2025-05-01": {}, "2025-05-02": {}, "2025-05-03": {}, "2025-05-04": {}, "2025-05-05": {},
	"2025-05-31": {}, "2025-06-01": {}, "2025-06-02": {},
	"2025-10-01": {}, "2025-10-02": {}, "2025-10-03": {}, "2025-10-04": {},
	"2025-10-05": {}, "2025-10-06": {}, "2025-10-07": {}, "2025-10-08": {},
	"2026-01-01": {}, "2026-01-02": {},
	"2026-02-15": {}, "2026-02-16": {}, "2026-02-17": {}, "2026-02-18": {},
	"2026-02-19": {}, "2026-02-20": {}, "2026-02-21": {}, "2026-02-22": {}, "2026-02-23": {},
	"2026-04-04": {}, "2026-04-05": {}, "2026-04-06": {},
	"2026-05-01": {}, "2026-05-02": {}, "2026-05-03": {}, "2026-05-04": {}, "2026-05-05": {},
	"2026-06-19": {}, "2026-06-20": {}, "2026-06-21": {},
	"2026-10-01": {}, "2026-10-02": {}, "2026-10-03": {}, "2026-10-04": {},
	"2026-10-05": {}, "2026-10-06": {}, "2026-10-07": {}, "2026-10-08": {},
	"2027-01-01": {},
}

var cnMakeup = map[string]struct{}{
	"2025-01-26": {}, "2025-02-08": {}, "2025-04-27": {}, "2025-09-28": {}, "2025-10-11": {},
	"2026-02-14": {}, "2026-02-28": {}, "2026-09-27": {}, "2026-10-10": {},
}

func dateKey(d time.Time) string { return d.Format("2006-01-02") }

func TodayCN(now time.Time) time.Time {
	if now.IsZero() {
		now = time.Now()
	}
	return now.In(cnLocation)
}

func IsWeekday(d time.Time) bool {
	w := d.Weekday()
	return w != time.Saturday && w != time.Sunday
}

func IsCNTradingDay(d time.Time) bool {
	key := dateKey(d)
	if _, ok := cnHolidays[key]; ok {
		return false
	}
	if _, ok := cnMakeup[key]; ok {
		return true
	}
	return IsWeekday(d)
}

func NextCNTradingDay(d time.Time) time.Time {
	cursor := d.AddDate(0, 0, 1)
	for i := 0; i < 20; i++ {
		if IsCNTradingDay(cursor) {
			return cursor
		}
		cursor = cursor.AddDate(0, 0, 1)
	}
	return cursor
}

func isUSOvernightOrderSession(et time.Time) bool {
	weekday := et.Weekday()
	h, m, _ := et.Clock()
	mins := h*60 + m
	end := 3*60 + 50
	overnight := 20 * 60
	if weekday <= time.Friday && mins < end {
		return true
	}
	if mins >= overnight && (weekday == time.Sunday || weekday <= time.Thursday) {
		return true
	}
	return false
}

func IsUSTradeSessionOpen(et time.Time) bool {
	if isUSOvernightOrderSession(et) {
		return true
	}
	if et.Weekday() == time.Saturday || et.Weekday() == time.Sunday {
		return false
	}
	h, m, _ := et.Clock()
	mins := h*60 + m
	return mins >= 4*60 && mins < 20*60
}

func USOutsideRTHMode(now time.Time) string {
	if now.IsZero() {
		now = time.Now()
	}
	et := now.In(usLocation)
	if isUSOvernightOrderSession(et) {
		return "overnight"
	}
	return "anytime"
}

// IsMarketSessionOpen matches Python is_market_session_open.
func IsMarketSessionOpen(market string, now time.Time) bool {
	if now.IsZero() {
		now = time.Now()
	}
	mkt := market
	if mkt == "" {
		mkt = "US"
	}
	switch mkt {
	case "US":
		return IsUSTradeSessionOpen(now.In(usLocation))
	case "HK":
		local := now.In(hkLocation)
		if !IsWeekday(local) {
			return false
		}
		h, m, _ := local.Clock()
		mins := h*60 + m
		return mins >= 9*60+30 && mins <= 16*60
	case "CN":
		local := now.In(cnLocation)
		if !IsCNTradingDay(local) {
			return false
		}
		h, m, _ := local.Clock()
		mins := h*60 + m
		return mins >= 9*60+30 && mins <= 15*60
	default:
		return IsUSTradeSessionOpen(now.In(usLocation))
	}
}

func BeijingNow() string {
	return time.Now().In(cnLocation).Format("2006-01-02 15:04:05")
}

func BeijingDate() string {
	return time.Now().In(cnLocation).Format("2006-01-02")
}
