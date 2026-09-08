package store

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	tradeexec "github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/lusd2904/smart-finance-platform/services/data-api/internal/longbridge"
)

var contentTTL = map[string]time.Duration{
	"announcement": 240 * time.Minute,
	"news":         60 * time.Minute,
	"topic":        30 * time.Minute,
}

var htmlTagRe = regexp.MustCompile(`(?is)<(script|style)[^>]*>.*?</(script|style)>|<[^>]+>`)
var spaceRe = regexp.MustCompile(`\s+`)

func normalizeContentType(raw string) string {
	key := strings.ToLower(strings.TrimSpace(raw))
	switch key {
	case "announcement", "announcements", "filings":
		return "announcement"
	case "topic", "topics":
		return "topic"
	default:
		return "news"
	}
}

func (d *DB) GetSymbolContent(ctx context.Context, symbol, market, contentType string, limit int, refresh bool) (map[string]interface{}, error) {
	symbol = strings.ToUpper(strings.TrimSpace(symbol))
	market = strings.ToUpper(strings.TrimSpace(market))
	contentType = normalizeContentType(contentType)
	limit = clamp(limit, 1, 50)
	if refresh {
		if err := d.refreshSymbolContent(ctx, symbol, market, contentType); err != nil {
			return nil, err
		}
	} else {
		items, _ := d.listCachedContent(ctx, symbol, contentType, limit)
		if len(items) == 0 {
			if err := d.refreshSymbolContent(ctx, symbol, market, contentType); err != nil {
				return nil, err
			}
		}
	}
	items, err := d.listCachedContent(ctx, symbol, contentType, limit)
	if err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"symbol": symbol, "market": market, "contentType": contentType,
		"items": items, "count": len(items), "source": "longbridge",
	}, nil
}

func (d *DB) listCachedContent(ctx context.Context, symbol, contentType string, limit int) ([]map[string]interface{}, error) {
	rows, err := d.sql.QueryContext(ctx, `
SELECT title, summary, source_link, published_at, source_item_id
FROM symbol_content_cache
WHERE symbol = ? AND content_type = ? AND (expires_at IS NULL OR expires_at > NOW())
ORDER BY published_at DESC LIMIT ?`, symbol, contentType, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []map[string]interface{}{}
	for rows.Next() {
		var title, summary, link, itemID sql.NullString
		var published sql.NullTime
		if err := rows.Scan(&title, &summary, &link, &published, &itemID); err != nil {
			return nil, err
		}
		items = append(items, map[string]interface{}{
			"id": nullStr(itemID), "title": nullStr(title), "summary": nullStr(summary),
			"content": nullStr(summary), "sourceLink": nullStr(link),
			"publishedAt": fmtTime(published),
		})
	}
	return items, rows.Err()
}

func (d *DB) refreshSymbolContent(ctx context.Context, symbol, market, contentType string) error {
	creds, err := d.loadAdminLongbridgeCreds(ctx)
	if err != nil || !creds.Configured() {
		return fmt.Errorf("长桥凭据未配置")
	}
	cli := longbridge.NewClient(creds)
	bundle, err := cli.FetchSymbolContent(ctx, longbridge.ToSymbol(symbol, market), []string{contentType})
	if err != nil {
		return err
	}
	httpClient := &http.Client{Timeout: 15 * time.Second}
	now := time.Now()
	for _, item := range bundle[contentType] {
		summary := stripHTML(item.Description)
		link := strings.TrimSpace(item.URL)
		if link != "" && len(summary) < 80 {
			if fetched := fetchPageText(httpClient, link); len(fetched) > len(summary) {
				summary = fetched
			}
		}
		if len(summary) > 12000 {
			summary = summary[:12000]
		}
		payload, _ := json.Marshal(item.Raw)
		if len(payload) > 60000 {
			payload = payload[:60000]
		}
		ttl := contentTTL[contentType]
		if ttl == 0 {
			ttl = time.Hour
		}
		_, err := d.sql.ExecContext(ctx, `
INSERT INTO symbol_content_cache (
  symbol, market, content_type, source_name, source_item_id, title, summary,
  source_link, published_at, fetched_at, expires_at, payload_json
) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
ON DUPLICATE KEY UPDATE
  title=VALUES(title), summary=VALUES(summary), source_link=VALUES(source_link),
  published_at=VALUES(published_at), fetched_at=VALUES(fetched_at),
  expires_at=VALUES(expires_at), payload_json=VALUES(payload_json)`,
			symbol, market, contentType, "longbridge", truncate(item.ID, 128), truncate(item.Title, 255), summary,
			nullString(link), nullTimePtr(item.PublishedAt), now, now.Add(ttl), string(payload))
		if err != nil {
			return err
		}
	}
	return nil
}

func (d *DB) loadAdminLongbridgeCreds(ctx context.Context) (longbridge.Creds, error) {
	var appKey, secret, token, region sql.NullString
	err := d.sql.QueryRowContext(ctx, `
SELECT app_key, app_secret, access_token, region FROM quant_longbridge_config
WHERE app_key IS NOT NULL AND app_key != '' ORDER BY user_id ASC LIMIT 1`).Scan(&appKey, &secret, &token, &region)
	if err != nil {
		env := longbridge.LoadCredsFromEnv()
		if env.Configured() {
			return env, nil
		}
		return longbridge.Creds{}, err
	}
	credKey, jwtSecret, appEnv := tradeexec.EncryptionKeysFromEnv()
	return longbridge.Creds{
		AppKey:      strings.TrimSpace(appKey.String),
		AppSecret:   tradeexec.DecryptOrRaw(secret.String, credKey, jwtSecret, appEnv),
		AccessToken: tradeexec.DecryptOrRaw(token.String, credKey, jwtSecret, appEnv),
		Region:      strings.TrimSpace(region.String),
	}, nil
}

func stripHTML(text string) string {
	return strings.TrimSpace(htmlTagRe.ReplaceAllString(text, " "))
}

func fetchPageText(client *http.Client, rawURL string) string {
	req, err := http.NewRequest(http.MethodGet, rawURL, nil)
	if err != nil {
		return ""
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (compatible; sfp-data-api/1.0)")
	resp, err := client.Do(req)
	if err != nil {
		return ""
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return ""
	}
	body, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return ""
	}
	text := stripHTML(string(body))
	text = strings.TrimSpace(spaceRe.ReplaceAllString(text, " "))
	if len(text) < 80 {
		return ""
	}
	if len(text) > 12000 {
		text = text[:12000]
	}
	return text
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func nullTimePtr(t *time.Time) interface{} {
	if t == nil {
		return nil
	}
	return *t
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
