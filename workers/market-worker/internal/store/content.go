package store

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/longbridge"
)

var hotSymbols = []struct {
	Symbol string
	Market string
}{
	{"AAPL", "US"},
	{"NVDA", "US"},
	{"MSFT", "US"},
	{"TSLA", "US"},
	{"0700", "HK"},
	{"9988", "HK"},
}

var contentTTL = map[string]time.Duration{
	"announcement": 240 * time.Minute,
	"news":         60 * time.Minute,
	"topic":        30 * time.Minute,
}

var htmlTagReContent = regexp.MustCompile(`(?is)<(script|style)[^>]*>.*?</(script|style)>|<[^>]+>`)
var spaceRe = regexp.MustCompile(`\s+`)

const (
	minSummaryFetch = 80
	minBodyLen      = 80
	bodyMaxLen      = 12000
)

func (s *Service) RefreshSymbolContent(ctx context.Context) (map[string]interface{}, error) {
	creds := longbridge.Creds{
		AppKey:      s.cfg.LongbridgeAppKey,
		AppSecret:   s.cfg.LongbridgeAppSecret,
		AccessToken: s.cfg.LongbridgeAccessToken,
		Region:      s.cfg.LongbridgeRegion,
		HTTPURL:     s.cfg.LongbridgeHTTPURL,
	}
	if !creds.Configured() {
		return map[string]interface{}{"skipped": true, "reason": "unconfigured", "total": 0}, nil
	}
	cli := longbridge.NewClient(creds)
	httpClient := &http.Client{Timeout: 15 * time.Second}
	total := 0
	for _, hot := range hotSymbols {
		n, err := s.refreshOneSymbol(ctx, cli, httpClient, hot.Symbol, hot.Market)
		if err != nil {
			continue
		}
		total += n
	}
	_, _ = s.db.ExecContext(ctx, `DELETE FROM symbol_content_cache WHERE expires_at IS NOT NULL AND expires_at < ?`, time.Now().Add(-72*time.Hour))
	return map[string]interface{}{"total": total}, nil
}

func (s *Service) refreshOneSymbol(ctx context.Context, cli *longbridge.Client, httpClient *http.Client, symbol, market string) (int, error) {
	lb := longbridge.ToSymbol(symbol, market)
	bundle, err := cli.FetchSymbolContent(ctx, lb, []string{"announcement", "news", "topic"})
	if err != nil {
		return 0, err
	}
	now := time.Now()
	saved := 0
	for ctype, items := range bundle {
		ttl := contentTTL[ctype]
		if ttl == 0 {
			ttl = time.Hour
		}
		expires := now.Add(ttl)
		for _, item := range items {
			summary := stripHTML(item.Description)
			link := strings.TrimSpace(item.URL)
			if link != "" && len(summary) < minSummaryFetch {
				if fetched := fetchPageText(httpClient, link); len(fetched) > len(summary) {
					summary = fetched
				}
			}
			if len(summary) > bodyMaxLen {
				summary = summary[:bodyMaxLen]
			}
			payload, _ := json.Marshal(item.Raw)
			if len(payload) > 60000 {
				payload = payload[:60000]
			}
			title := item.Title
			if len(title) > 255 {
				title = title[:255]
			}
			id := item.ID
			if len(id) > 128 {
				id = id[:128]
			}
			if link != "" && len(link) > 1000 {
				link = link[:1000]
			}
			if _, err := s.db.ExecContext(ctx, `
INSERT INTO symbol_content_cache (
  symbol, market, content_type, source_name, source_item_id, title, summary,
  source_link, published_at, fetched_at, expires_at, payload_json
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
ON DUPLICATE KEY UPDATE
  title=VALUES(title), summary=VALUES(summary), source_link=VALUES(source_link),
  published_at=VALUES(published_at), fetched_at=VALUES(fetched_at),
  expires_at=VALUES(expires_at), payload_json=VALUES(payload_json)`,
				symbol, market, ctype, "longbridge", id, title, summary,
				nullString(link), nullTime(item.PublishedAt), now, expires, string(payload),
			); err != nil {
				return saved, fmt.Errorf("upsert content %s: %w", symbol, err)
			}
			saved++
		}
	}
	return saved, nil
}

func fetchPageText(client *http.Client, rawURL string) string {
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return ""
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
	resp, err := client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return ""
	}
	ctype := strings.ToLower(resp.Header.Get("Content-Type"))
	if !strings.Contains(ctype, "html") && !strings.Contains(ctype, "text") && !strings.Contains(ctype, "json") {
		return ""
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return ""
	}
	text := stripHTML(string(body))
	text = strings.TrimSpace(spaceRe.ReplaceAllString(text, " "))
	if len(text) < minBodyLen {
		return ""
	}
	if len(text) > bodyMaxLen {
		text = text[:bodyMaxLen]
	}
	return text
}

func stripHTML(text string) string {
	return strings.TrimSpace(htmlTagReContent.ReplaceAllString(text, " "))
}

func nullString(s string) any {
	if strings.TrimSpace(s) == "" {
		return nil
	}
	return s
}

func nullTime(v *time.Time) any {
	if v == nil {
		return nil
	}
	return *v
}
