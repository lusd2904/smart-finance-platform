package influx

import (
	"bytes"
	"context"
	"encoding/csv"
	"fmt"
	"io"
	"net/http"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/config"
)

var (
	symbolPattern = regexp.MustCompile(`^[A-Za-z0-9.^_-]{1,32}$`)
	relTimePattern = regexp.MustCompile(`^-\d{1,4}(s|m|h|d|w|mo|y)$`)
)

const (
	measurementDaily = "daily_kline"
	latestChunkSize  = 30
)

type KlineBar struct {
	Date   string
	Open   float64
	High   float64
	Low    float64
	Close  float64
	Volume float64
}

type Reader struct {
	cfg    config.Config
	client *http.Client
}

func NewReader(cfg config.Config) *Reader {
	return &Reader{
		cfg:    cfg,
		client: &http.Client{Timeout: 60 * time.Second},
	}
}

func (r *Reader) QueryLatestKlines(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]KlineBar, error) {
	safe := sanitizeSymbols(symbols)
	if len(safe) == 0 {
		return map[string][]KlineBar{}, nil
	}
	if n <= 0 {
		n = 2
	}
	if start == "" {
		start = "-60d"
	}
	out := map[string][]KlineBar{}
	for i := 0; i < len(safe); i += latestChunkSize {
		end := i + latestChunkSize
		if end > len(safe) {
			end = len(safe)
		}
		chunk, err := r.queryLatestChunk(ctx, market, safe[i:end], n, start)
		if err != nil {
			return nil, err
		}
		for sym, bars := range chunk {
			out[sym] = bars
		}
	}
	return out, nil
}

// QueryKlinesMany fetches up to `limit` daily bars per symbol (chunked).
func (r *Reader) QueryKlinesMany(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]KlineBar, error) {
	if limit <= 0 {
		limit = 320
	}
	if start == "" {
		start = "-1y"
	}
	return r.QueryLatestKlines(ctx, market, symbols, limit, start)
}

func (r *Reader) QueryKlines(ctx context.Context, market, symbol, start string, limit int) ([]KlineBar, error) {
	sym := sanitizeSymbol(symbol)
	if sym == "" {
		return nil, nil
	}
	startClause, ok := safeTimeClause(start)
	if !ok {
		return nil, nil
	}
	if limit <= 0 {
		limit = 8
	}
	bucket := r.cfg.BucketForMarket(market)
	flux := fmt.Sprintf(`
from(bucket: "%s")
  |> range(start: %s, stop: now())
  |> filter(fn: (r) => r._measurement == "%s")
  |> filter(fn: (r) => r.symbol == "%s")
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
  |> tail(n: %d)
`, bucket, startClause, measurementDaily, sym, limit)
	grouped, err := r.runFlux(ctx, flux)
	if err != nil {
		return nil, err
	}
	return grouped[sym], nil
}

func (r *Reader) ListSymbols(ctx context.Context, market string) ([]string, error) {
	bucket := r.cfg.BucketForMarket(market)
	mkt := strings.ToUpper(market)
	var flux string
	if mkt == "US" {
		flux = fmt.Sprintf(`import "influxdata/influxdb/schema"
schema.tagValues(bucket: "%s", tag: "symbol")`, bucket)
	} else {
		flux = fmt.Sprintf(`import "influxdata/influxdb/schema"
schema.tagValues(bucket: "%s", tag: "symbol", predicate: (r) => r["market"] == "%s")`, bucket, mkt)
	}
	records, err := r.queryRecords(ctx, flux)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	var out []string
	for _, rec := range records {
		val := strings.TrimSpace(rec["_value"])
		if val == "" || val == "symbol" || val == "_value" || val == "_result" || strings.HasPrefix(val, "#") {
			continue
		}
		if strings.Contains(val, ",") {
			parts := strings.Split(val, ",")
			val = strings.TrimSpace(parts[len(parts)-1])
		}
		if val == "" || seen[val] {
			continue
		}
		seen[val] = true
		out = append(out, val)
	}
	sort.Strings(out)
	return out, nil
}

func (r *Reader) queryLatestChunk(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]KlineBar, error) {
	startClause, ok := safeTimeClause(start)
	if !ok {
		return map[string][]KlineBar{}, nil
	}
	bucket := r.cfg.BucketForMarket(market)
	clause := symbolOrClause(symbols)
	flux := fmt.Sprintf(`
from(bucket: "%s")
  |> range(start: %s, stop: now())
  |> filter(fn: (r) => r._measurement == "%s")
  |> filter(fn: (r) => %s)
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group(columns: ["symbol"])
  |> sort(columns: ["_time"])
  |> tail(n: %d)
`, bucket, startClause, measurementDaily, clause, n)
	return r.runFlux(ctx, flux)
}

func (r *Reader) runFlux(ctx context.Context, flux string) (map[string][]KlineBar, error) {
	records, err := r.queryRecords(ctx, flux)
	if err != nil {
		return nil, err
	}
	grouped := map[string][]KlineBar{}
	for _, rec := range records {
		sym := strings.TrimSpace(rec["symbol"])
		if sym == "" {
			continue
		}
		ts := strings.TrimSpace(rec["_time"])
		date := ts
		if len(ts) >= 10 {
			date = ts[:10]
		}
		bar := KlineBar{
			Date:   date,
			Open:   parseFloat(rec["open"]),
			High:   parseFloat(rec["high"]),
			Low:    parseFloat(rec["low"]),
			Close:  parseFloat(rec["close"]),
			Volume: parseFloat(rec["volume"]),
		}
		grouped[sym] = append(grouped[sym], bar)
	}
	for sym := range grouped {
		sort.Slice(grouped[sym], func(i, j int) bool {
			return grouped[sym][i].Date < grouped[sym][j].Date
		})
	}
	return grouped, nil
}

func (r *Reader) queryRecords(ctx context.Context, flux string) ([]map[string]string, error) {
	endpoint := fmt.Sprintf("%s/api/v2/query?org=%s",
		strings.TrimRight(r.cfg.InfluxURL, "/"),
		urlEscape(r.cfg.InfluxOrg),
	)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, endpoint, bytes.NewReader([]byte(flux)))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Token "+r.cfg.InfluxToken)
	req.Header.Set("Content-Type", "application/vnd.flux")
	req.Header.Set("Accept", "application/csv")
	resp, err := r.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("influx query %d: %s", resp.StatusCode, string(body))
	}
	return parseFluxCSV(body)
}

func parseFluxCSV(raw []byte) ([]map[string]string, error) {
	reader := csv.NewReader(bytes.NewReader(raw))
	reader.FieldsPerRecord = -1
	rows, err := reader.ReadAll()
	if err != nil {
		return nil, err
	}
	if len(rows) == 0 {
		return nil, nil
	}
	headerIdx := -1
	for i, row := range rows {
		if len(row) > 0 && row[0] == "#datatype" {
			continue
		}
		if len(row) > 0 && row[0] == "result" {
			headerIdx = i
			break
		}
	}
	if headerIdx < 0 {
		return nil, nil
	}
	header := rows[headerIdx]
	var out []map[string]string
	for _, row := range rows[headerIdx+1:] {
		if len(row) == 0 || row[0] == "" {
			continue
		}
		rec := map[string]string{}
		for i, col := range header {
			if i >= len(row) {
				break
			}
			rec[col] = row[i]
		}
		if rec["_field"] != "" && rec["_value"] != "" {
			// long format row — skip, pivot queries return wide rows
			continue
		}
		if rec["symbol"] == "" && rec["_time"] == "" {
			continue
		}
		out = append(out, rec)
	}
	return out, nil
}

func sanitizeSymbol(symbol string) string {
	text := strings.TrimSpace(symbol)
	if symbolPattern.MatchString(text) {
		return text
	}
	return ""
}

func sanitizeSymbols(symbols []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, raw := range symbols {
		s := sanitizeSymbol(raw)
		if s == "" || seen[s] {
			continue
		}
		seen[s] = true
		out = append(out, s)
	}
	return out
}

func symbolOrClause(symbols []string) string {
	parts := make([]string, 0, len(symbols))
	for _, s := range symbols {
		parts = append(parts, fmt.Sprintf(`r.symbol == "%s"`, s))
	}
	return strings.Join(parts, " or ")
}

func safeTimeClause(value string) (string, bool) {
	text := strings.TrimSpace(value)
	if text == "" || text == "now()" || text == "0" || relTimePattern.MatchString(text) {
		return text, true
	}
	if len(text) >= 10 && text[4] == '-' {
		return fmt.Sprintf(`time(v: "%s")`, text), true
	}
	return "", false
}

func parseFloat(v string) float64 {
	f, _ := strconv.ParseFloat(strings.TrimSpace(v), 64)
	return f
}

func urlEscape(v string) string {
	return strings.ReplaceAll(v, " ", "%20")
}
