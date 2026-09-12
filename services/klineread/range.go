package klineread

import (
	"regexp"
	"strconv"
	"strings"
	"time"
)

var (
	symbolPattern = regexp.MustCompile(`^[A-Za-z0-9.^_-]{1,32}$`)
	relTimePattern = regexp.MustCompile(`^-(\d{1,4})(s|m|h|d|w|mo|y)$`)
	beijing       = time.FixedZone("CST", 8*3600)
)

const maxQueryLimit = 5000

func nowBeijing() time.Time {
	return time.Now().In(beijing)
}

func SanitizeSymbol(symbol string) string {
	s := strings.TrimSpace(symbol)
	if symbolPattern.MatchString(s) {
		return s
	}
	return ""
}

func sanitizeSymbols(symbols []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, raw := range symbols {
		s := SanitizeSymbol(raw)
		if s == "" || seen[s] {
			continue
		}
		seen[s] = true
		out = append(out, s)
	}
	return out
}

func normalizeMarket(market string) string {
	return strings.ToUpper(strings.TrimSpace(market))
}

// symbolLookupOrder returns the exact requested symbol first, then an uppercase
// variant when that differs. It never appends exchange suffixes, so 000001
// (上证) is not remapped to 000001.SZ (平安).
func symbolLookupOrder(symbol string) []string {
	s := SanitizeSymbol(symbol)
	if s == "" {
		return nil
	}
	out := []string{s}
	if u := strings.ToUpper(s); u != s {
		out = append(out, u)
	}
	return out
}

func clampLimit(limit *int) int {
	if limit == nil {
		return 0
	}
	n := *limit
	if n < 1 {
		return 0
	}
	if n > maxQueryLimit {
		return maxQueryLimit
	}
	return n
}

func parseBound(value string, now time.Time) (time.Time, bool) {
	text := strings.TrimSpace(value)
	if text == "" || text == "now()" || text == "0" {
		return now, true
	}
	if m := relTimePattern.FindStringSubmatch(text); m != nil {
		n, err := strconv.Atoi(m[1])
		if err != nil {
			return time.Time{}, false
		}
		switch m[2] {
		case "s":
			return now.Add(-time.Duration(n) * time.Second), true
		case "m":
			return now.Add(-time.Duration(n) * time.Minute), true
		case "h":
			return now.Add(-time.Duration(n) * time.Hour), true
		case "d":
			return now.AddDate(0, 0, -n), true
		case "w":
			return now.AddDate(0, 0, -7*n), true
		case "mo":
			return now.AddDate(0, -n, 0), true
		case "y":
			return now.AddDate(-n, 0, 0), true
		}
		return time.Time{}, false
	}
	if t, err := time.Parse(time.RFC3339Nano, text); err == nil {
		return t.In(beijing), true
	}
	if t, err := time.Parse(time.RFC3339, text); err == nil {
		return t.In(beijing), true
	}
	layouts := []string{
		"2006-01-02 15:04:05",
		"2006-01-02 15:04",
		"2006-01-02T15:04:05",
		"2006-01-02T15:04",
		"2006-01-02",
	}
	for _, layout := range layouts {
		if t, err := time.ParseInLocation(layout, text, beijing); err == nil {
			return t, true
		}
	}
	return time.Time{}, false
}

func resolveRange(start, stop string, now time.Time) (from, to time.Time, ok bool) {
	from, ok1 := parseBound(start, now)
	to, ok2 := parseBound(stop, now)
	if !ok1 || !ok2 {
		return time.Time{}, time.Time{}, false
	}
	return from, to, true
}

func formatDailyDate(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.In(beijing).Format("2006-01-02")
}

func formatMinuteDate(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.In(beijing).Format("2006-01-02 15:04")
}

func formatMinuteSQL(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	return t.In(beijing).Format("2006-01-02 15:04:05")
}

func lastNBars(bars []Bar, limit int) []Bar {
	if limit <= 0 || len(bars) <= limit {
		return bars
	}
	return bars[len(bars)-limit:]
}
