package longbridge

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

type Creds struct {
	AppKey      string
	AppSecret   string
	AccessToken string
	Region      string
	HTTPURL     string
}

func (c Creds) Configured() bool {
	return c.AppKey != "" && c.AppSecret != "" && c.AccessToken != ""
}

func (c Creds) BaseURL() string {
	if strings.TrimSpace(c.HTTPURL) != "" {
		return strings.TrimRight(c.HTTPURL, "/")
	}
	if strings.EqualFold(c.Region, "cn") || c.Region == "" {
		return "https://openapi.longbridge.cn"
	}
	return "https://openapi.longbridge.com"
}

func LoadCredsFromEnv() Creds {
	return Creds{
		AppKey:      firstEnv("LONGPORT_APP_KEY", "LONGBRIDGE_APP_KEY"),
		AppSecret:   firstEnv("LONGPORT_APP_SECRET", "LONGBRIDGE_APP_SECRET"),
		AccessToken: firstEnv("LONGPORT_ACCESS_TOKEN", "LONGBRIDGE_ACCESS_TOKEN"),
		Region:      firstEnv("LONGPORT_REGION", "LONGBRIDGE_REGION"),
		HTTPURL:     firstEnv("LONGPORT_HTTP_URL", "LONGBRIDGE_HTTP_URL"),
	}
}

func firstEnv(keys ...string) string {
	for _, key := range keys {
		if v := strings.TrimSpace(os.Getenv(key)); v != "" {
			return v
		}
	}
	return ""
}

func ToSymbol(symbol, market string) string {
	raw := strings.ToUpper(strings.TrimSpace(symbol))
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if raw == "" {
		return raw
	}
	if strings.Contains(raw, ".") || strings.HasPrefix(raw, "^") {
		return raw
	}
	suffix := mkt
	switch mkt {
	case "US":
		suffix = "US"
	case "HK":
		suffix = "HK"
	case "CN":
		suffix = "SH"
		if isDigits(raw) && !strings.HasPrefix(raw, "6") {
			suffix = "SZ"
		}
	}
	return raw + "." + suffix
}

type Item struct {
	ID          string
	Title       string
	Description string
	URL         string
	PublishedAt *time.Time
	Raw         map[string]any
}

type Client struct {
	HTTP  *http.Client
	Creds Creds
	Now   func() time.Time
}

func NewClient(creds Creds) *Client {
	return &Client{
		HTTP:  &http.Client{Timeout: 20 * time.Second},
		Creds: creds,
		Now:   time.Now,
	}
}

func (c *Client) FetchSymbolContent(ctx context.Context, lbSymbol string, types []string) (map[string][]Item, error) {
	out := map[string][]Item{}
	for _, t := range types {
		out[t] = []Item{}
	}
	if !c.Creds.Configured() {
		return out, nil
	}
	need := map[string]bool{}
	for _, t := range types {
		need[t] = true
	}
	if need["announcement"] {
		items, err := c.getItems(ctx, "/v1/quote/filings", url.Values{"symbol": {lbSymbol}}, true)
		if err != nil {
			return out, err
		}
		out["announcement"] = items
	}
	if need["news"] {
		items, err := c.getItems(ctx, "/v1/content/"+url.PathEscape(lbSymbol)+"/news", nil, false)
		if err != nil {
			return out, err
		}
		out["news"] = items
	}
	if need["topic"] {
		items, err := c.getItems(ctx, "/v1/content/"+url.PathEscape(lbSymbol)+"/topics", nil, false)
		if err != nil {
			return out, err
		}
		out["topic"] = items
	}
	return out, nil
}

func (c *Client) getItems(ctx context.Context, path string, query url.Values, filings bool) ([]Item, error) {
	qs := ""
	if query != nil {
		qs = query.Encode()
	}
	raw, err := c.getJSON(ctx, path, qs)
	if err != nil {
		return nil, err
	}
	data := asMap(raw["data"])
	rows := asList(data["items"])
	out := make([]Item, 0, len(rows))
	for _, row := range rows {
		m := asMap(row)
		item := Item{
			ID:          firstString(m, "id", "news_id", "topic_id", "filing_id"),
			Title:       firstString(m, "title", "title_cn", "headline"),
			Description: firstString(m, "description", "content", "summary"),
			URL:         firstString(m, "url", "link", "source_link"),
			Raw:         m,
		}
		if filings {
			if item.URL == "" {
				if urls := asList(m["file_urls"]); len(urls) > 0 {
					item.URL = fmt.Sprint(urls[0])
				}
			}
			item.PublishedAt = parseUnix(m["publish_at"])
		} else {
			item.PublishedAt = parseUnix(m["published_at"])
		}
		if item.Title == "" {
			continue
		}
		if item.ID == "" {
			item.ID = item.Title
		}
		out = append(out, item)
	}
	return out, nil
}

func (c *Client) getJSON(ctx context.Context, path, query string) (map[string]any, error) {
	full := c.Creds.BaseURL() + path
	if query != "" {
		full += "?" + query
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, full, nil)
	if err != nil {
		return nil, err
	}
	ts := strconv.FormatInt(c.Now().UnixMilli(), 10)
	req.Header.Set("x-api-key", c.Creds.AppKey)
	req.Header.Set("authorization", c.Creds.AccessToken)
	req.Header.Set("x-timestamp", ts)
	req.Header.Set("x-api-signature", SignRequest(http.MethodGet, path, query, "", c.Creds.AppKey, c.Creds.AccessToken, ts, c.Creds.AppSecret))
	req.Header.Set("Accept", "application/json")
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return nil, fmt.Errorf("longbridge HTTP %d: %s", resp.StatusCode, truncate(string(body), 200))
	}
	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, err
	}
	code := 0
	switch v := payload["code"].(type) {
	case float64:
		code = int(v)
	case json.Number:
		n, _ := v.Int64()
		code = int(n)
	}
	if code != 0 {
		return nil, fmt.Errorf("longbridge code=%v message=%v", payload["code"], payload["message"])
	}
	return payload, nil
}

func isDigits(s string) bool {
	if s == "" {
		return false
	}
	for i := 0; i < len(s); i++ {
		if s[i] < '0' || s[i] > '9' {
			return false
		}
	}
	return true
}

func asMap(v any) map[string]any {
	if m, ok := v.(map[string]any); ok {
		return m
	}
	return map[string]any{}
}

func asList(v any) []any {
	if list, ok := v.([]any); ok {
		return list
	}
	return nil
}

func firstString(m map[string]any, keys ...string) string {
	for _, key := range keys {
		if v, ok := m[key]; ok && v != nil {
			s := strings.TrimSpace(fmt.Sprint(v))
			if s != "" && s != "<nil>" {
				return s
			}
		}
	}
	return ""
}

func parseUnix(v any) *time.Time {
	if v == nil {
		return nil
	}
	var ts int64
	switch x := v.(type) {
	case float64:
		ts = int64(x)
	case json.Number:
		n, err := x.Int64()
		if err != nil {
			return nil
		}
		ts = n
	case string:
		s := strings.TrimSpace(x)
		if s == "" {
			return nil
		}
		n, err := strconv.ParseInt(s, 10, 64)
		if err != nil {
			return nil
		}
		ts = n
	default:
		return nil
	}
	if ts > 1e12 {
		ts /= 1000
	}
	if ts <= 0 {
		return nil
	}
	tm := time.Unix(ts, 0)
	return &tm
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
