package influx

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/kline"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/timeutil"
)

const (
	measurementDaily  = "daily_kline"
	measurementMinute = "minute_kline"
	maxQueryLimit     = 5000
)

var (
	symbolPattern       = regexp.MustCompile(`^[A-Za-z0-9.^_-]{1,32}$`)
	relativeTimePattern = regexp.MustCompile(`^-\d{1,4}(s|m|h|d|w|mo|y)$`)
	rfc3339Pattern      = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:?\d{2})?)?$`)
)

type Client struct {
	cfg    *config.Config
	client *http.Client
}

func New(cfg *config.Config) *Client {
	timeout := cfg.InfluxTimeout
	if timeout <= 0 {
		timeout = 8 * time.Second
	}
	return &Client{
		cfg: cfg,
		client: &http.Client{Timeout: timeout},
	}
}

func (c *Client) Close() {}

func bucketForMarket(cfg *config.Config, market string) string {
	if strings.ToUpper(market) == "US" {
		return cfg.InfluxBucketUS
	}
	return cfg.InfluxBucketCN
}

func (c *Client) QueryKlines(ctx context.Context, market, symbol, start, stop string, limit *int) ([]kline.Bar, error) {
	safeSymbol := safeSymbol(symbol)
	startClause := safeTimeClause(start)
	stopClause := safeTimeClause(stop)
	if safeSymbol == "" || startClause == "" || stopClause == "" {
		return []kline.Bar{}, nil
	}
	tail := ""
	if limit != nil && *limit >= 1 && *limit <= maxQueryLimit {
		tail = fmt.Sprintf("\n  |> tail(n: %d)", *limit)
	}
	flux := fmt.Sprintf(`
from(bucket: "%s")
  |> range(start: %s, stop: %s)
  |> filter(fn: (r) => r._measurement == "%s")
  |> filter(fn: (r) => r.symbol == "%s")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])%s`, bucketForMarket(c.cfg, market), startClause, stopClause, measurementDaily, safeSymbol, tail)
	return c.queryBars(ctx, flux, false)
}

func (c *Client) QueryMinuteKlines(ctx context.Context, market, symbol, start, stop string, limit *int) ([]kline.Bar, error) {
	safeSymbol := safeSymbol(symbol)
	startClause := safeTimeClause(start)
	stopClause := safeTimeClause(stop)
	if safeSymbol == "" || startClause == "" || stopClause == "" {
		return []kline.Bar{}, nil
	}
	tail := ""
	if limit != nil && *limit >= 1 && *limit <= maxQueryLimit {
		tail = fmt.Sprintf("\n  |> tail(n: %d)", *limit)
	}
	flux := fmt.Sprintf(`
from(bucket: "%s")
  |> range(start: %s, stop: %s)
  |> filter(fn: (r) => r._measurement == "%s")
  |> filter(fn: (r) => r.symbol == "%s")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])%s`, bucketForMarket(c.cfg, market), startClause, stopClause, measurementMinute, safeSymbol, tail)
	return c.queryBars(ctx, flux, true)
}

func (c *Client) GetKlineSeries(ctx context.Context, market, symbol, period, start, stop string, limit *int) ([]kline.Bar, error) {
	p := kline.NormalizePeriod(period)
	start = kline.DefaultRangeStart(p, start)
	lim := kline.DefaultLimit(p, limit)
	if kline.IsMinutePeriod(p) {
		bars, err := c.QueryMinuteKlines(ctx, market, symbol, start, stop, lim)
		if err != nil {
			return nil, err
		}
		if how := kline.MinuteResampleRule(p); how != "" && len(bars) > 0 {
			return kline.ResampleMinuteBars(bars, how), nil
		}
		return bars, nil
	}
	bars, err := c.QueryKlines(ctx, market, symbol, start, stop, lim)
	if err != nil {
		return nil, err
	}
	if how := kline.DailyResampleRule(p); how != "" {
		return kline.ResampleDailyBars(bars, how), nil
	}
	return bars, nil
}

type fluxTable struct {
	Records []fluxRecord `json:"records"`
}

type fluxRecord struct {
	Time  time.Time              `json:"_time"`
	Value map[string]interface{} `json:"values"`
}

func (c *Client) queryBars(ctx context.Context, flux string, minute bool) ([]kline.Bar, error) {
	body, err := c.postFlux(ctx, flux)
	if err != nil {
		return nil, err
	}
	tables := parseFluxCSV(body)
	bars := make([]kline.Bar, 0)
	for _, rec := range tables {
		ts := rec.Time
		date := timeutil.FormatDate(ts)
		if minute {
			date = timeutil.FormatBeijingMinute(ts)
		}
		bars = append(bars, kline.Bar{
			Date:   date,
			Open:   floatPtr(rec.Value["open"]),
			High:   floatPtr(rec.Value["high"]),
			Low:    floatPtr(rec.Value["low"]),
			Close:  floatPtr(rec.Value["close"]),
			Volume: floatPtr(rec.Value["volume"]),
		})
	}
	return bars, nil
}

func (c *Client) postFlux(ctx context.Context, flux string) ([]byte, error) {
	url := strings.TrimRight(c.cfg.InfluxURL, "/") + "/api/v2/query?org=" + c.cfg.InfluxOrg
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBufferString(flux))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Token "+c.cfg.InfluxToken)
	req.Header.Set("Content-Type", "application/vnd.flux")
	req.Header.Set("Accept", "application/csv")
	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("influx query failed: %s", string(data))
	}
	return data, nil
}

// parseFluxCSV parses annotated CSV from Influx query API into records.
func parseFluxCSV(data []byte) []fluxRecord {
	lines := strings.Split(string(data), "\n")
	headers := []string{}
	records := make([]fluxRecord, 0)
	for _, line := range lines {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if strings.HasPrefix(line, "#") {
			continue
		}
		if strings.HasPrefix(line, ",result,table") {
			headers = splitCSV(line)
			continue
		}
		if len(headers) == 0 {
			continue
		}
		fields := splitCSV(line)
		if len(fields) != len(headers) {
			continue
		}
		vals := map[string]interface{}{}
		var ts time.Time
		for i, h := range headers {
			v := fields[i]
			switch h {
			case "_time":
				if t, err := time.Parse(time.RFC3339Nano, v); err == nil {
					ts = t
				}
			case "_field":
				// skip pivot rows handled below
			default:
				if h == "open" || h == "high" || h == "low" || h == "close" || h == "volume" {
					if f, err := parseFloat(v); err == nil {
						vals[h] = f
					}
				}
			}
		}
		// pivoted rows have open/high/low/close/volume as columns
		for _, key := range []string{"open", "high", "low", "close", "volume"} {
			if idx := indexOf(headers, key); idx >= 0 && idx < len(fields) {
				if f, err := parseFloat(fields[idx]); err == nil {
					vals[key] = f
				}
			}
		}
		if !ts.IsZero() && len(vals) > 0 {
			records = append(records, fluxRecord{Time: ts, Value: vals})
		}
	}
	return records
}

func splitCSV(line string) []string {
	parts := strings.Split(line, ",")
	for i := range parts {
		parts[i] = strings.Trim(parts[i], "\"")
	}
	return parts
}

func indexOf(items []string, target string) int {
	for i, v := range items {
		if v == target {
			return i
		}
	}
	return -1
}

func parseFloat(s string) (float64, error) {
	if s == "" {
		return 0, fmt.Errorf("empty")
	}
	var f float64
	_, err := fmt.Sscan(s, &f)
	return f, err
}

func safeSymbol(symbol string) string {
	s := strings.TrimSpace(symbol)
	if symbolPattern.MatchString(s) {
		return s
	}
	return ""
}

func safeTimeClause(value string) string {
	text := strings.TrimSpace(value)
	if text == "now()" || text == "0" || relativeTimePattern.MatchString(text) {
		return text
	}
	if rfc3339Pattern.MatchString(text) {
		return fmt.Sprintf(`time(v: "%s")`, text)
	}
	return ""
}

func floatPtr(v interface{}) *float64 {
	switch n := v.(type) {
	case float64:
		return &n
	case int64:
		f := float64(n)
		return &f
	default:
		return nil
	}
}

// parseFluxCSV parses annotated CSV from Influx query API into records.