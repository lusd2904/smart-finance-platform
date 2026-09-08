package ingest

import (
	"crypto/hmac"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"regexp"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/timeutil"
)

const BatchMax = 200

var topicSplit = regexp.MustCompile(`[,，|/]+`)

type Item struct {
	PostedAt string      `json:"postedAt"`
	Author   string      `json:"author"`
	AuthorID string      `json:"authorId"`
	Text     string      `json:"text"`
	URL      string      `json:"url"`
	Topics   interface{} `json:"topics"`
	Source   string      `json:"source"`
}

type MappedNews struct {
	Source    string
	Title     string
	Content   string
	URL       *string
	PubTime   time.Time
	UniqHash  string
	Analyzed  string
	CreateTime time.Time
}

func VerifyToken(provided, expected string) error {
	expected = strings.TrimSpace(expected)
	provided = strings.TrimSpace(provided)
	if expected == "" {
		return fmt.Errorf("ingest token is not configured")
	}
	if provided == "" {
		return fmt.Errorf("missing ingest token")
	}
	left := []byte(provided)
	right := []byte(expected)
	if len(left) != len(right) {
		hmac.Equal(right, right)
		return fmt.Errorf("invalid ingest token")
	}
	if !hmac.Equal(left, right) {
		return fmt.Errorf("invalid ingest token")
	}
	return nil
}

func NormalizeTopics(topics interface{}) []string {
	if topics == nil {
		return nil
	}
	switch v := topics.(type) {
	case []interface{}:
		out := make([]string, 0, len(v))
		for _, raw := range v {
			s := strings.TrimSpace(fmt.Sprint(raw))
			if s != "" {
				out = append(out, s)
			}
		}
		return out
	case []string:
		out := make([]string, 0, len(v))
		for _, s := range v {
			s = strings.TrimSpace(s)
			if s != "" {
				out = append(out, s)
			}
		}
		return out
	default:
		text := strings.TrimSpace(fmt.Sprint(v))
		if text == "" {
			return nil
		}
		parts := topicSplit.Split(text, -1)
		out := make([]string, 0, len(parts))
		for _, p := range parts {
			p = strings.TrimSpace(p)
			if p != "" {
				out = append(out, p)
			}
		}
		return out
	}
}

func MapXMonitorItem(raw map[string]interface{}) *MappedNews {
	if raw == nil {
		return nil
	}
	text := strings.TrimSpace(fmt.Sprint(raw["text"]))
	url := strings.TrimSpace(fmt.Sprint(raw["url"]))
	if url == "<nil>" {
		url = ""
	}
	if text == "<nil>" {
		text = ""
	}
	if text == "" && url == "" {
		return nil
	}
	firstLine := text
	if firstLine != "" {
		if idx := strings.IndexByte(firstLine, '\n'); idx >= 0 {
			firstLine = firstLine[:idx]
		}
	} else {
		firstLine = url
	}
	title := firstLine
	if len(title) > 80 {
		title = title[:80]
	}
	if title == "" {
		if len(url) > 80 {
			title = url[:80]
		} else {
			title = url
		}
	}
	if title == "" {
		title = "x_monitor"
	}
	topics := NormalizeTopics(raw["topics"])
	content := text
	if content == "" {
		content = title
	}
	if len(topics) > 0 {
		tag := strings.Join(topics, ",")
		content = fmt.Sprintf("%s\n[topics:%s]", content, tag)
	}
	author := strings.TrimSpace(fmt.Sprint(raw["author"]))
	if author != "" && author != "<nil>" && !strings.Contains(content, "@"+author) {
		content = "@" + author + ": " + content
	}
	var uniq string
	if url != "" {
		sum := md5.Sum([]byte(url))
		uniq = hex.EncodeToString(sum[:])
	} else {
		sum := md5.Sum([]byte("x_monitor:" + text))
		uniq = hex.EncodeToString(sum[:])
	}
	postedAt := ""
	if v, ok := raw["posted_at"].(string); ok {
		postedAt = v
	} else if v, ok := raw["postedAt"].(string); ok {
		postedAt = v
	}
	var urlPtr *string
	if url != "" {
		urlPtr = &url
	}
	return &MappedNews{
		Source:   "x_monitor",
		Title:    truncate(title, 500),
		Content:  truncate(content, 4000),
		URL:      urlPtr,
		PubTime:  timeutil.ParseFlexible(postedAt),
		UniqHash: uniq,
	}
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func URLHash(url string) string {
	sum := md5.Sum([]byte(url))
	return hex.EncodeToString(sum[:])
}
