package newscollect

import (
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"html"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/lusd2904/smart-finance-platform/workers/notify-worker/internal/timeutil"
)

const (
	DefaultSources = "eastmoney,sina,ths,wallstreetcn,google_news"
	UserAgent      = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
	titleMax       = 500
	contentMax     = 4000
)

var htmlTagRe = regexp.MustCompile(`(?s)<[^>]+>`)

// Item is one sentiment_news row ready for insert (analyzed is set by the worker).
type Item struct {
	Source   string
	Title    string
	Content  string
	URL      string
	PubTime  time.Time
	UniqHash string
}

type SourceResult struct {
	Source  string `json:"source"`
	Fetched int    `json:"fetched"`
	Error   string `json:"error,omitempty"`
	Skipped string `json:"skipped,omitempty"`
}

func SplitSources(raw string) []string {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		raw = DefaultSources
	}
	parts := strings.Split(raw, ",")
	out := make([]string, 0, len(parts))
	seen := map[string]bool{}
	for _, p := range parts {
		key := strings.ToLower(strings.TrimSpace(p))
		if key == "" || seen[key] {
			continue
		}
		seen[key] = true
		out = append(out, key)
	}
	if len(out) == 0 {
		return strings.Split(DefaultSources, ",")
	}
	return out
}

func MakeHash(source, key string) string {
	sum := md5.Sum([]byte(source + ":" + key))
	return hex.EncodeToString(sum[:])
}

func StripHTML(text string) string {
	text = htmlTagRe.ReplaceAllString(text, "")
	return strings.TrimSpace(html.UnescapeString(text))
}

func Truncate(s string, n int) string {
	if n <= 0 || s == "" {
		return s
	}
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

func ParseTime(value any) time.Time {
	now := timeutil.NowShanghai()
	switch v := value.(type) {
	case time.Time:
		if v.IsZero() {
			return now
		}
		return v.In(timeutil.Shanghai)
	case int:
		return unixToShanghai(int64(v))
	case int64:
		return unixToShanghai(v)
	case float64:
		return unixToShanghai(int64(v))
	case json.Number:
		n, err := v.Int64()
		if err != nil {
			f, ferr := v.Float64()
			if ferr != nil {
				return ParseTime(v.String())
			}
			return unixToShanghai(int64(f))
		}
		return unixToShanghai(n)
	default:
		text := strings.TrimSpace(fmt.Sprint(value))
		if text == "" || text == "<nil>" {
			return now
		}
		if n, err := strconv.ParseInt(text, 10, 64); err == nil && n > 1e8 {
			return unixToShanghai(n)
		}
		if t, ok := parseTimeString(text); ok {
			return t
		}
		return now
	}
}

func unixToShanghai(ts int64) time.Time {
	if ts <= 0 {
		return timeutil.NowShanghai()
	}
	if ts >= 1e12 {
		ts = ts / 1000
	}
	return time.Unix(ts, 0).In(timeutil.Shanghai)
}

func parseTimeString(text string) (time.Time, bool) {
	iso := strings.Replace(text, "Z", "+00:00", 1)
	if t, err := time.Parse(time.RFC3339, iso); err == nil {
		return t.In(timeutil.Shanghai), true
	}
	naive := []string{
		"2006-01-02 15:04:05",
		"2006-01-02T15:04:05",
		"2006-01-02",
	}
	for _, layout := range naive {
		if t, err := time.ParseInLocation(layout, text, timeutil.Shanghai); err == nil {
			return t, true
		}
	}
	rfc := []string{
		time.RFC1123,
		time.RFC1123Z,
		"Mon, 02 Jan 2006 15:04:05",
		"Mon, 2 Jan 2006 15:04:05 MST",
		"Mon, 2 Jan 2006 15:04:05 -0700",
	}
	for _, layout := range rfc {
		if t, err := time.Parse(layout, text); err == nil {
			return t.In(timeutil.Shanghai), true
		}
	}
	if len(text) >= 25 {
		if t, err := time.Parse("Mon, 02 Jan 2006 15:04:05", text[:25]); err == nil {
			return t.In(timeutil.Shanghai), true
		}
	}
	return time.Time{}, false
}

func asString(v any) string {
	if v == nil {
		return ""
	}
	switch t := v.(type) {
	case string:
		return strings.TrimSpace(t)
	case json.Number:
		return t.String()
	case float64:
		if t == float64(int64(t)) {
			return strconv.FormatInt(int64(t), 10)
		}
		return strconv.FormatFloat(t, 'f', -1, 64)
	case int:
		return strconv.Itoa(t)
	case int64:
		return strconv.FormatInt(t, 10)
	default:
		s := strings.TrimSpace(fmt.Sprint(t))
		if s == "<nil>" {
			return ""
		}
		return s
	}
}

func FilterFresh(items []Item, existing map[string]bool) []Item {
	if existing == nil {
		existing = map[string]bool{}
	}
	out := make([]Item, 0, len(items))
	seen := map[string]bool{}
	for _, item := range items {
		if item.UniqHash == "" || existing[item.UniqHash] || seen[item.UniqHash] {
			continue
		}
		seen[item.UniqHash] = true
		out = append(out, item)
	}
	return out
}

func Summarize(fetched, saved, pending, windowMinutes int, reports []SourceResult) string {
	var fails []string
	ingestOnly := 0
	ok := 0
	for _, r := range reports {
		if r.Error != "" {
			fails = append(fails, r.Source+" 失败: "+r.Error)
			continue
		}
		switch r.Skipped {
		case "ingest-only":
			ingestOnly++
		case "unknown", "alias-of-ths":
			// not a successful public fetch
		default:
			ok++
		}
	}
	var b strings.Builder
	if fetched == 0 && saved == 0 && ok == 0 && ingestOnly > 0 && len(fails) == 0 {
		b.WriteString("x_monitor 仅走 ingest，本轮未拉取公开源。")
	} else if fetched == 0 && saved == 0 {
		b.WriteString("资讯源暂无新内容或上游不可用。")
	} else {
		fmt.Fprintf(&b, "采集 %d 条，新入库 %d 条。", fetched, saved)
	}
	if len(fails) > 0 {
		b.WriteString("（" + strings.Join(fails, "；") + "）")
	}
	fmt.Fprintf(&b, "最近 %d 分钟待分析 %d 条。", windowMinutes, pending)
	return b.String()
}
