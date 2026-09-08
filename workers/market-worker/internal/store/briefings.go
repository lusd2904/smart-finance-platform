package store

import (
	"context"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/indicators"
)

var htmlTagRe = regexp.MustCompile(`<[^>]+>`)

type briefingRow struct {
	Market       string
	BriefingType string
	Headline     string
	Summary      string
	SourceName   string
	SourceLink   *string
	PayloadJSON  string
	GeneratedAt  time.Time
	ExpiresAt    time.Time
}

var marketLabels = map[string]string{
	"US": "美股",
	"CN": "A股",
	"HK": "港股",
}

var externalNewsQueries = map[string]string{
	"US": "US stock market OR Nasdaq OR S&P 500 OR Federal Reserve",
	"CN": "A-share market OR China stocks OR CSI 300 OR Shanghai Composite",
	"HK": "Hong Kong stocks OR Hang Seng OR China Hong Kong market",
}

var marketBenchmarks = map[string][][2]string{
	"US": {{"^GSPC", "S&P500"}, {"^IXIC", "Nasdaq"}, {"^DJI", "Dow"}},
}

var marketKeywords = map[string][]string{
	"US": {"美股", "纳斯达克", "道琼斯", "标普", "美联储", "华尔街", "Nasdaq", "Fed"},
	"CN": {"A股", "沪指", "深成指", "创业板", "科创板", "上证", "A 股"},
	"HK": {"港股", "恒生", "恒指", "港交所", "南向"},
}

func (s *Service) RefreshFinanceBriefings(ctx context.Context) (map[string]interface{}, error) {
	now := time.Now()
	generated := []briefingRow{}
	for _, market := range []string{"US", "CN", "HK"} {
		internal, err := s.buildInternalBriefings(ctx, market, now)
		if err == nil {
			generated = append(generated, internal...)
		}
		news, _ := s.fetchGoogleNews(ctx, market, now)
		generated = append(generated, news...)
		sentiment, _ := s.pullSentimentNews(ctx, market, now)
		generated = append(generated, sentiment...)
	}
	recs, _ := s.buildRecommendationBriefings(ctx, now)
	generated = append(generated, recs...)

	seen := map[string]bool{}
	deduped := []briefingRow{}
	for _, item := range generated {
		key := item.Market + "|" + item.BriefingType + "|" + item.Headline
		if seen[key] {
			continue
		}
		seen[key] = true
		deduped = append(deduped, item)
	}

	if len(deduped) > 0 {
		if err := s.insertBriefings(ctx, deduped); err != nil {
			return nil, err
		}
	}
	if err := s.pruneBriefings(ctx, now.Add(-5*24*time.Hour)); err != nil {
		return nil, err
	}
	return map[string]interface{}{
		"generatedAt": now.Format("2006-01-02 15:04:05"),
		"count":       len(deduped),
	}, nil
}

func (s *Service) buildInternalBriefings(ctx context.Context, market string, now time.Time) ([]briefingRow, error) {
	label := marketLabels[market]
	expires := now.Add(30 * time.Minute)
	items := []briefingRow{}
	benchmarks := marketBenchmarks[market]
	insightBits := []string{}
	var marketScore *float64
	for _, pair := range benchmarks {
		sym, name := pair[0], pair[1]
		bars, err := s.reader.QueryKlines(ctx, market, sym, "-30d", 8)
		if err != nil || len(bars) < 2 {
			continue
		}
		prev, last := bars[len(bars)-2], bars[len(bars)-1]
		if prev.Close <= 0 || last.Close <= 0 {
			continue
		}
		chg := (last.Close/prev.Close - 1) * 100
		insightBits = append(insightBits, fmt.Sprintf("%s %+.2f%%", name, chg))
		if marketScore == nil {
			v := round4(chg)
			marketScore = &v
		}
	}
	headline := label + "市场脉冲"
	summary := label + "暂无新的市场动态。"
	if len(insightBits) > 0 {
		summary = strings.Join(insightBits, "；")
	}
	payload, _ := json.Marshal(map[string]interface{}{
		"marketScore": marketScore,
		"benchmarks":  insightBits,
	})
	items = append(items, briefingRow{
		Market: market, BriefingType: "market-insight", Headline: headline, Summary: summary,
		SourceName: "market-insight", PayloadJSON: string(payload),
		GeneratedAt: now, ExpiresAt: expires,
	})

	if len(benchmarks) > 0 {
		sym, name := benchmarks[0][0], benchmarks[0][1]
		bars, err := s.reader.QueryKlines(ctx, market, sym, "-1y", 320)
		if err == nil && len(bars) > 0 {
			indBars := make([]indicators.Bar, len(bars))
			dates := make([]string, len(bars))
			for i, b := range bars {
				indBars[i] = indicators.Bar{Close: b.Close, High: b.High, Low: b.Low}
				dates[i] = b.Date
			}
			snap := indicators.LatestSnapshot(indBars, dates)
			techSummary := fmt.Sprintf("%s 技术扫描暂无数据", label)
			var techScore float64
			if snap.Has {
				techScore = indicators.TechScore(snap.RSI12, snap.MACD)
				rsiText := "--"
				if snap.RSI12 > 0 {
					rsiText = fmt.Sprintf("%.1f", snap.RSI12)
				}
				techSummary = fmt.Sprintf("%s 收盘%.4f，RSI=%s，技术评分%.1f", name, snap.Close, rsiText, techScore)
			}
			payload, _ := json.Marshal(map[string]interface{}{
				"technicalScore": techScore,
				"rsi":            snap.RSI12,
				"close":          snap.Close,
			})
			items = append(items, briefingRow{
				Market: market, BriefingType: "market-ai-scan", Headline: label + "技术扫描",
				Summary: techSummary, SourceName: "daily-market-scan", PayloadJSON: string(payload),
				GeneratedAt: now, ExpiresAt: expires,
			})
		}
	}
	return items, nil
}

func (s *Service) buildRecommendationBriefings(ctx context.Context, now time.Time) ([]briefingRow, error) {
	var runID int64
	err := s.db.QueryRowContext(ctx, `
SELECT run_id FROM quant_strategy_run ORDER BY create_time DESC LIMIT 1`).Scan(&runID)
	if err != nil {
		return nil, nil
	}
	rows, err := s.db.QueryContext(ctx, `
SELECT s.symbol, s.score, s.confidence, s.signal, s.reason, COALESCE(i.market, 'US') AS market
FROM quant_strategy_signal s
LEFT JOIN market_instrument i ON i.symbol = s.symbol
WHERE s.run_id = ? AND s.signal = 'BUY'
ORDER BY s.score DESC
LIMIT 3`, runID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	items := []briefingRow{}
	expires := now.Add(60 * time.Minute)
	for rows.Next() {
		var symbol, signal, reason, market string
		var score, confidence float64
		if err := rows.Scan(&symbol, &score, &confidence, &signal, &reason, &market); err != nil {
			continue
		}
		market = strings.ToUpper(market)
		label := marketLabels[market]
		if label == "" {
			label = market
		}
		payload, _ := json.Marshal(map[string]interface{}{
			"symbol": symbol, "score": score, "confidence": confidence, "signal": signal,
		})
		items = append(items, briefingRow{
			Market: market, BriefingType: "recommendation",
			Headline: fmt.Sprintf("%s推荐关注 %s", label, symbol),
			Summary:  reason,
			SourceName: "quant-strategy", PayloadJSON: string(payload),
			GeneratedAt: now, ExpiresAt: expires,
		})
	}
	return items, nil
}

func (s *Service) fetchGoogleNews(ctx context.Context, market string, now time.Time) ([]briefingRow, error) {
	query := externalNewsQueries[market]
	if query == "" {
		return nil, nil
	}
	newsURL := fmt.Sprintf("https://news.google.com/rss/search?q=%s&hl=zh-CN&gl=CN&ceid=CN:zh-Hans", url.QueryEscape(query))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, newsURL, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 RuoYi-Sentiment/1.0")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("google news http %d", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	type rssItem struct {
		Title       string `xml:"title"`
		Description string `xml:"description"`
		Link        string `xml:"link"`
	}
	type rssChannel struct {
		Items []rssItem `xml:"channel>item"`
	}
	var parsed rssChannel
	if err := xml.Unmarshal(body, &parsed); err != nil {
		return nil, err
	}
	expires := now.Add(90 * time.Minute)
	since := now.Add(-6 * time.Hour)
	items := []briefingRow{}
	for i, item := range parsed.Items {
		if i >= 5 {
			break
		}
		headline := truncate(item.Title, 190)
		if headline == "" {
			continue
		}
		dup, _ := s.briefingDuplicate(ctx, market, headline, since)
		if dup {
			continue
		}
		summary := truncate(htmlTagRe.ReplaceAllString(item.Description, ""), 800)
		link := strings.TrimSpace(item.Link)
		var linkPtr *string
		if link != "" {
			linkPtr = &link
		}
		payload, _ := json.Marshal(map[string]string{"kind": "external-news", "source": "google-news-rss"})
		items = append(items, briefingRow{
			Market: market, BriefingType: "market-news", Headline: headline, Summary: summary,
			SourceName: "Google News RSS", SourceLink: linkPtr, PayloadJSON: string(payload),
			GeneratedAt: now, ExpiresAt: expires,
		})
	}
	return items, nil
}

func (s *Service) pullSentimentNews(ctx context.Context, market string, now time.Time) ([]briefingRow, error) {
	keywords := marketKeywords[market]
	rows, err := s.db.QueryContext(ctx, `
SELECT title, content, source_name, source_url, pub_time
FROM sentiment_news
ORDER BY pub_time DESC
LIMIT 40`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	expires := now.Add(90 * time.Minute)
	since := now.Add(-6 * time.Hour)
	items := []briefingRow{}
	for rows.Next() {
		var title, content, sourceName string
		var sourceURL *string
		var pubTime time.Time
		if err := rows.Scan(&title, &content, &sourceName, &sourceURL, &pubTime); err != nil {
			continue
		}
		title = strings.TrimSpace(title)
		if title == "" {
			continue
		}
		text := title + " " + content
		if !matchesMarketKeyword(text, keywords) {
			continue
		}
		dup, _ := s.briefingDuplicate(ctx, market, title, since)
		if dup {
			continue
		}
		payload, _ := json.Marshal(map[string]string{"kind": "sentiment-news"})
		items = append(items, briefingRow{
			Market: market, BriefingType: "market-news", Headline: truncate(title, 190),
			Summary: truncate(content, 800), SourceName: sourceName, SourceLink: sourceURL,
			PayloadJSON: string(payload), GeneratedAt: now, ExpiresAt: expires,
		})
		if len(items) >= 5 {
			break
		}
	}
	return items, nil
}

func (s *Service) insertBriefings(ctx context.Context, rows []briefingRow) error {
	stmt := `
INSERT INTO finance_briefing
(market, briefing_type, headline, summary, source_name, source_link, payload_json, generated_at, expires_at, create_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())`
	for _, row := range rows {
		_, err := s.db.ExecContext(ctx, stmt,
			row.Market, row.BriefingType, truncate(row.Headline, 255), row.Summary,
			row.SourceName, row.SourceLink, row.PayloadJSON, row.GeneratedAt, row.ExpiresAt)
		if err != nil {
			return err
		}
	}
	return nil
}

func (s *Service) pruneBriefings(ctx context.Context, before time.Time) error {
	_, err := s.db.ExecContext(ctx, `DELETE FROM finance_briefing WHERE generated_at < ?`, before)
	return err
}

func (s *Service) briefingDuplicate(ctx context.Context, market, headline string, since time.Time) (bool, error) {
	var id int64
	err := s.db.QueryRowContext(ctx, `
SELECT id FROM finance_briefing
WHERE market = ? AND headline = ? AND generated_at >= ?
LIMIT 1`, market, headline, since).Scan(&id)
	if err != nil {
		return false, nil
	}
	return id > 0, nil
}

func matchesMarketKeyword(text string, keywords []string) bool {
	for _, kw := range keywords {
		if kw != "" && strings.Contains(text, kw) {
			return true
		}
	}
	return false
}

func truncate(text string, max int) string {
	text = strings.TrimSpace(text)
	if len(text) <= max {
		return text
	}
	return text[:max]
}
