package influx

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
)

type Writer struct {
	cfg    config.Config
	client *http.Client
}

type Bar struct {
	Symbol    string
	TradeDate time.Time
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
}

func NewWriter(cfg config.Config) (*Writer, error) {
	if cfg.InfluxToken == "" {
		return nil, fmt.Errorf("INFLUX_TOKEN is required")
	}
	return &Writer{
		cfg:    cfg,
		client: &http.Client{Timeout: 45 * time.Second},
	}, nil
}

func (w *Writer) Close() {}

func (w *Writer) WriteDaily(ctx context.Context, market string, rows []Bar) (int, error) {
	return w.write(ctx, market, "daily_kline", rows)
}

func (w *Writer) WriteMinute(ctx context.Context, market string, rows []Bar) (int, error) {
	return w.write(ctx, market, "minute_kline", rows)
}

func (w *Writer) write(ctx context.Context, market, measurement string, rows []Bar) (int, error) {
	if len(rows) == 0 {
		return 0, nil
	}
	bucket := w.cfg.BucketForMarket(market)
	mkt := strings.ToUpper(market)
	var buf bytes.Buffer
	for _, row := range rows {
		ts := row.TradeDate.Unix()
		line := fmt.Sprintf(
			"%s,symbol=%s,market=%s open=%f,high=%f,low=%f,close=%f,volume=%f %d\n",
			measurement,
			escapeTag(row.Symbol),
			escapeTag(mkt),
			row.Open, row.High, row.Low, row.Close, row.Volume,
			ts,
		)
		buf.WriteString(line)
	}
	endpoint := fmt.Sprintf("%s/api/v2/write?org=%s&bucket=%s&precision=s",
		strings.TrimRight(w.cfg.InfluxURL, "/"),
		urlEscape(w.cfg.InfluxOrg),
		urlEscape(bucket),
	)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader(buf.Bytes()))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Authorization", "Token "+w.cfg.InfluxToken)
	req.Header.Set("Content-Type", "text/plain; charset=utf-8")
	resp, err := w.client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return 0, fmt.Errorf("influx write %d: %s", resp.StatusCode, string(body))
	}
	return len(rows), nil
}

func escapeTag(v string) string {
	return strings.NewReplacer(",", "\\,", " ", "\\ ", "=", "\\=").Replace(v)
}

func urlEscape(v string) string {
	return strings.ReplaceAll(v, " ", "%20")
}

func ParseDate(s string) (time.Time, error) {
	text := strings.TrimSpace(s)
	if len(text) >= 10 {
		text = text[:10]
	}
	return time.Parse("2006-01-02", text)
}

func ParseMinute(s string) (time.Time, error) {
	text := strings.TrimSpace(strings.ReplaceAll(s, "T", " "))
	if len(text) >= 19 {
		return time.Parse("2006-01-02 15:04:05", text[:19])
	}
	if len(text) >= 16 {
		return time.Parse("2006-01-02 15:04", text[:16])
	}
	return time.Time{}, fmt.Errorf("invalid minute timestamp: %s", s)
}
