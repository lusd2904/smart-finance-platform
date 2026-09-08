package timeutil

import (
	"time"
)

var beijing = time.FixedZone("CST", 8*3600)

func NowBeijing() time.Time {
	return time.Now().In(beijing)
}

func NowBeijingRFC() string {
	return NowBeijing().Format("2006-01-02 15:04:05")
}

func FormatBeijing(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	if t.Location() == time.UTC {
		t = t.In(beijing)
	}
	return t.Format("2006-01-02 15:04:05")
}

func FormatBeijingMinute(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	if t.Location() == time.UTC {
		t = t.In(beijing)
	}
	return t.Format("2006-01-02 15:04")
}

func FormatDate(t time.Time) string {
	if t.IsZero() {
		return ""
	}
	if t.Location() == time.UTC {
		t = t.In(beijing)
	}
	return t.Format("2006-01-02")
}
