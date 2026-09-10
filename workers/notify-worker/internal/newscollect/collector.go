package newscollect

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	httpTimeout   = 25 * time.Second
	maxBodyBytes  = 4 << 20
	eastmoneySize = 50
	sinaSize      = 50
	thsSize       = 40
	wscnSize      = 40
	jin10Size     = 40
	googleSize    = 30
)

var googleQueries = []string{
	"美股 OR 纳斯达克 OR 美联储",
	"A股 OR 上证 OR 港股",
	"原油 OR 黄金 OR 通胀",
}

// Supported public sources. x_monitor is ingest-only and never fetched here.
var Supported = map[string]bool{
	"eastmoney":    true,
	"sina":         true,
	"ths":          true,
	"cls":          true, // alias of ths
	"wallstreetcn": true,
	"google_news":  true,
	"jin10":        true,
}

type Client struct {
	HTTP    *http.Client
	Rewrite func(canonical string) string
}

func NewClient() *Client {
	return &Client{
		HTTP: &http.Client{
			Timeout: httpTimeout,
			Transport: &http.Transport{
				Proxy:                 nil,
				TLSHandshakeTimeout:   10 * time.Second,
				ResponseHeaderTimeout: 20 * time.Second,
				IdleConnTimeout:       30 * time.Second,
			},
		},
	}
}

func (c *Client) http() *http.Client {
	if c != nil && c.HTTP != nil {
		return c.HTTP
	}
	return NewClient().HTTP
}

func (c *Client) url(canonical string) string {
	if c != nil && c.Rewrite != nil {
		return c.Rewrite(canonical)
	}
	return canonical
}

func Collect(ctx context.Context, client *Client, sources []string) ([]Item, []SourceResult) {
	if client == nil {
		client = NewClient()
	}
	sources = SplitSources(strings.Join(sources, ","))
	fetchedTHS := false
	all := make([]Item, 0, 128)
	reports := make([]SourceResult, 0, len(sources))
	for _, name := range sources {
		switch name {
		case "x_monitor":
			reports = append(reports, SourceResult{Source: name, Skipped: "ingest-only"})
			continue
		case "cls":
			if fetchedTHS {
				reports = append(reports, SourceResult{Source: name, Skipped: "alias-of-ths"})
				continue
			}
		}
		if !Supported[name] {
			slog.Warn("sentiment collect unknown source", "source", name)
			reports = append(reports, SourceResult{Source: name, Skipped: "unknown"})
			continue
		}
		items, err := client.fetchSource(ctx, name)
		if name == "ths" || name == "cls" {
			fetchedTHS = true
		}
		if err != nil {
			slog.Warn("sentiment collect source failed", "source", name, "err", err)
			reports = append(reports, SourceResult{Source: name, Error: err.Error()})
			continue
		}
		reports = append(reports, SourceResult{Source: name, Fetched: len(items)})
		all = append(all, items...)
	}
	return dedupItems(all), reports
}

func (c *Client) fetchSource(ctx context.Context, name string) ([]Item, error) {
	switch name {
	case "eastmoney":
		return c.fetchEastmoney(ctx)
	case "sina":
		return c.fetchSina(ctx)
	case "ths", "cls":
		return c.fetchTHS(ctx)
	case "wallstreetcn":
		return c.fetchWallstreetCN(ctx)
	case "google_news":
		return c.fetchGoogleNews(ctx)
	case "jin10":
		return c.fetchJin10(ctx)
	default:
		return nil, fmt.Errorf("unknown source %s", name)
	}
}

func (c *Client) fetchEastmoney(ctx context.Context) ([]Item, error) {
	canonical := "https://np-listapi.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=" +
		strconv.Itoa(eastmoneySize) + "&req_trace=" + strconv.FormatInt(time.Now().UnixMilli(), 10)
	body, err := c.get(ctx, canonical, "https://kuaixun.eastmoney.com/")
	if err != nil {
		return nil, err
	}
	return parseEastmoney(body), nil
}

func (c *Client) fetchSina(ctx context.Context) ([]Item, error) {
	canonical := "https://zhibo.sina.com.cn/api/zhibo/feed?page=1&page_size=" +
		strconv.Itoa(sinaSize) + "&zhibo_id=152&tag_id=0&dire=f&dpc=1"
	body, err := c.get(ctx, canonical, "https://finance.sina.com.cn/7x24/")
	if err != nil {
		return nil, err
	}
	return parseSina(body), nil
}

func (c *Client) fetchTHS(ctx context.Context) ([]Item, error) {
	canonical := "https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=" +
		strconv.Itoa(thsSize)
	body, err := c.get(ctx, canonical, "https://news.10jqka.com.cn/")
	if err != nil {
		return nil, err
	}
	return parseTHS(body), nil
}

func (c *Client) fetchWallstreetCN(ctx context.Context) ([]Item, error) {
	canonical := "https://api-one-wscn.awtmt.com/apiv1/content/lives?channel=global-channel&limit=" +
		strconv.Itoa(wscnSize) + "&client=pc"
	body, err := c.get(ctx, canonical, "https://wallstreetcn.com/live/global")
	if err != nil {
		return nil, err
	}
	return parseWallstreetCN(body), nil
}

func (c *Client) fetchJin10(ctx context.Context) ([]Item, error) {
	canonical := "https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1&max_time="
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.url(canonical), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", UserAgent)
	req.Header.Set("Referer", "https://www.jin10.com/")
	req.Header.Set("x-app-id", "bVBF4FyRTn5NJF5n")
	req.Header.Set("x-version", "1.0.0")
	body, err := c.do(req)
	if err != nil {
		return nil, err
	}
	items := parseJin10(body)
	if len(items) > jin10Size {
		items = items[:jin10Size]
	}
	return items, nil
}

func (c *Client) fetchGoogleNews(ctx context.Context) ([]Item, error) {
	perQuery := googleSize / len(googleQueries)
	if perQuery < 5 {
		perQuery = 5
	}
	out := make([]Item, 0, googleSize)
	var lastErr error
	for _, q := range googleQueries {
		canonical := "https://news.google.com/rss/search?q=" + url.QueryEscape(q) + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
		body, err := c.get(ctx, canonical, "")
		if err != nil {
			slog.Warn("sentiment collect google_news query failed", "q", q, "err", err)
			lastErr = err
			continue
		}
		out = append(out, parseGoogleNewsRSS(body, perQuery)...)
	}
	if len(out) == 0 && lastErr != nil {
		return nil, lastErr
	}
	return out, nil
}

func (c *Client) get(ctx context.Context, canonical, referer string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.url(canonical), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", UserAgent)
	if referer != "" {
		req.Header.Set("Referer", referer)
	}
	return c.do(req)
}

func (c *Client) do(req *http.Request) ([]byte, error) {
	resp, err := c.http().Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBodyBytes))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("http %d", resp.StatusCode)
	}
	return body, nil
}

func dedupItems(items []Item) []Item {
	return FilterFresh(items, nil)
}
