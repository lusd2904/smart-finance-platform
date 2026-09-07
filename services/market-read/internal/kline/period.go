package kline

import (
	"sort"
	"strings"
	"time"
)

var aliases = map[string]string{
	"intraday": "intraday", "timeshare": "intraday", "time": "intraday", "ts": "intraday", "分时": "intraday",
	"1min": "1min", "1m": "1min", "min1": "1min", "1分": "1min",
	"5min": "5min", "5m": "5min", "min5": "5min", "5分": "5min",
	"15min": "15min", "15m": "15min", "min15": "15min", "15分": "15min",
	"daily": "daily", "day": "daily", "d": "daily", "1d": "daily", "日": "daily", "日k": "daily",
	"weekly": "weekly", "week": "weekly", "w": "weekly", "1w": "weekly", "周": "weekly", "周k": "weekly",
	"monthly": "monthly", "month": "monthly", "mo": "monthly", "1mo": "monthly", "月": "monthly", "月k": "monthly",
}

var minutePeriods = map[string]bool{"intraday": true, "1min": true, "5min": true, "15min": true}

var defaultStart = map[string]string{
	"intraday": "-1d", "1min": "-2d", "5min": "-5d", "15min": "-10d",
	"daily": "-2y", "weekly": "-3y", "monthly": "-5y",
}

var defaultLimit = map[string]int{
	"intraday": 500, "1min": 2000, "5min": 1500, "15min": 800,
	"daily": 800, "weekly": 800, "monthly": 1500,
}

type Bar struct {
	Date   string
	Open   *float64
	High   *float64
	Low    *float64
	Close  *float64
	Volume *float64
}

func NormalizePeriod(raw string) string {
	text := strings.ToLower(strings.TrimSpace(raw))
	if text == "" {
		return "daily"
	}
	if v, ok := aliases[text]; ok {
		return v
	}
	return "daily"
}

func IsMinutePeriod(period string) bool {
	return minutePeriods[NormalizePeriod(period)]
}

func DefaultRangeStart(period, current string) string {
	start := strings.TrimSpace(current)
	if start != "" && start != "-2y" {
		return start
	}
	if v, ok := defaultStart[NormalizePeriod(period)]; ok {
		return v
	}
	return "-2y"
}

func DefaultLimit(period string, current *int) *int {
	if current != nil {
		n := *current
		if n <= 0 {
			v := defaultLimit[NormalizePeriod(period)]
			return &v
		}
		if n > 5000 {
			n = 5000
		}
		return &n
	}
	v := defaultLimit[NormalizePeriod(period)]
	return &v
}

func MinuteResampleRule(period string) string {
	switch NormalizePeriod(period) {
	case "5min":
		return "5min"
	case "15min":
		return "15min"
	default:
		return ""
	}
}

func DailyResampleRule(period string) string {
	switch NormalizePeriod(period) {
	case "weekly":
		return "W"
	case "monthly":
		return "M"
	default:
		return ""
	}
}

func ResampleMinuteBars(bars []Bar, how string) []Bar {
	if len(bars) == 0 {
		return bars
	}
	minutes := 5
	if how == "15min" {
		minutes = 15
	}
	type bucket struct {
		open, high, low, close, volume float64
		hasOpen, hasClose              bool
		date                           string
	}
	buckets := make(map[int64]*bucket)
	keys := make([]int64, 0)
	for _, bar := range bars {
		t, err := time.Parse("2006-01-02 15:04", bar.Date)
		if err != nil {
			continue
		}
		key := t.Unix() / int64(minutes*60)
		b := buckets[key]
		if b == nil {
			b = &bucket{date: t.Truncate(time.Duration(minutes) * time.Minute).Format("2006-01-02 15:04")}
			buckets[key] = b
			keys = append(keys, key)
		}
		o, h, l, c, v := vals(bar)
		if !b.hasOpen {
			b.open = o
			b.hasOpen = true
		}
		if h > b.high || !b.hasOpen {
			b.high = h
		}
		if !b.hasOpen || l < b.low {
			b.low = l
		}
		b.close = c
		b.hasClose = true
		b.volume += v
	}
	sort.Slice(keys, func(i, j int) bool { return keys[i] < keys[j] })
	out := make([]Bar, 0, len(keys))
	for _, key := range keys {
		b := buckets[key]
		if !b.hasClose {
			continue
		}
		out = append(out, Bar{
			Date: b.date, Open: &b.open, High: &b.high, Low: &b.low, Close: &b.close, Volume: &b.volume,
		})
	}
	return out
}

func ResampleDailyBars(bars []Bar, how string) []Bar {
	if len(bars) == 0 || how == "D" {
		return bars
	}
	type bucket struct {
		open, high, low, close, volume float64
		hasOpen, hasClose              bool
		date                           string
	}
	buckets := make(map[string]*bucket)
	keys := make([]string, 0)
	for _, bar := range bars {
		t, err := time.Parse("2006-01-02", bar.Date)
		if err != nil {
			continue
		}
		key := weekKey(t)
		if how == "M" {
			key = t.Format("2006-01")
		}
		b := buckets[key]
		if b == nil {
			label := t.Format("2006-01-02")
			if how == "M" {
				label = t.Format("2006-01") + "-01"
			}
			b = &bucket{date: label}
			buckets[key] = b
			keys = append(keys, key)
		}
		o, h, l, c, v := vals(bar)
		if !b.hasOpen {
			b.open = o
			b.hasOpen = true
		}
		if h > b.high || !b.hasOpen {
			b.high = h
		}
		if !b.hasOpen || l < b.low {
			b.low = l
		}
		b.close = c
		b.hasClose = true
		b.volume += v
	}
	sort.Strings(keys)
	out := make([]Bar, 0, len(keys))
	for _, key := range keys {
		b := buckets[key]
		if !b.hasClose {
			continue
		}
		out = append(out, Bar{
			Date: b.date, Open: &b.open, High: &b.high, Low: &b.low, Close: &b.close, Volume: &b.volume,
		})
	}
	return out
}

func weekKey(t time.Time) string {
	year, week := t.ISOWeek()
	return fmtWeek(year, week)
}

func fmtWeek(year, week int) string {
	return strings.TrimSpace(strings.Join([]string{itoa(year), "W", itoa(week)}, ""))
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var b [20]byte
	i := len(b)
	for n > 0 {
		i--
		b[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		b[i] = '-'
	}
	return string(b[i:])
}

func vals(bar Bar) (float64, float64, float64, float64, float64) {
	o := 0.0
	if bar.Open != nil {
		o = *bar.Open
	}
	h := 0.0
	if bar.High != nil {
		h = *bar.High
	}
	l := 0.0
	if bar.Low != nil {
		l = *bar.Low
	}
	c := 0.0
	if bar.Close != nil {
		c = *bar.Close
	}
	v := 0.0
	if bar.Volume != nil {
		v = *bar.Volume
	}
	return o, h, l, c, v
}
