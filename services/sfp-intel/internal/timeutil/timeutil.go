package timeutil

import "time"

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

func ParseFlexible(s string) time.Time {
	s = stringsTrim(s)
	if s == "" {
		return NowBeijing()
	}
	if t, err := time.ParseInLocation(time.RFC3339, stringsReplaceZ(s), beijing); err == nil {
		return t
	}
	for _, layout := range []string{
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05",
		"2006-01-02",
	} {
		if t, err := time.ParseInLocation(layout, s, beijing); err == nil {
			return t
		}
	}
	return NowBeijing()
}

func stringsTrim(s string) string {
	i, j := 0, len(s)
	for i < j && (s[i] == ' ' || s[i] == '\t' || s[i] == '\n') {
		i++
	}
	for j > i && (s[j-1] == ' ' || s[j-1] == '\t' || s[j-1] == '\n') {
		j--
	}
	return s[i:j]
}

func stringsReplaceZ(s string) string {
	if len(s) > 0 && s[len(s)-1] == 'Z' {
		return s[:len(s)-1] + "+00:00"
	}
	return s
}
