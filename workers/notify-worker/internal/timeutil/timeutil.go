package timeutil

import (
	"log/slog"
	"strings"
	"time"

	_ "time/tzdata" // embed IANA zoneinfo for static/Alpine images
)

const ShanghaiTZ = "Asia/Shanghai"

// Shanghai is the Asia/Shanghai location, or CST+8 if zoneinfo is unavailable.
var Shanghai = loadLocation(ShanghaiTZ, "CST", 8*3600)

func loadLocation(name, fallbackName string, offsetSec int) *time.Location {
	loc, err := time.LoadLocation(name)
	if err != nil {
		slog.Default().Warn("timezone unavailable, using fixed offset",
			"name", name, "fallback", fallbackName, "err", err)
		return time.FixedZone(fallbackName, offsetSec)
	}
	return loc
}

// LocationFor returns the named timezone, or Shanghai when name is empty or invalid.
func LocationFor(name string) *time.Location {
	name = strings.TrimSpace(name)
	if name == "" {
		return Shanghai
	}
	loc, err := time.LoadLocation(name)
	if err != nil {
		slog.Default().Warn("timezone unavailable, falling back to Shanghai",
			"name", name, "err", err)
		return Shanghai
	}
	return loc
}

func InShanghai(t time.Time) time.Time {
	return t.In(Shanghai)
}

func NowShanghai() time.Time {
	return time.Now().In(Shanghai)
}

func FormatShanghai(t time.Time) string {
	return t.In(Shanghai).Format("2006-01-02 15:04:05")
}

// IsCNTradingDay reports whether now falls on a weekday in China (Mon–Fri).
func IsCNTradingDay(now time.Time) bool {
	wd := InShanghai(now).Weekday()
	return wd != time.Saturday && wd != time.Sunday
}
