package store

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/factor"
	mwinflux "github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/influx"
)

const (
	boardTTL    = 15 * time.Minute
	factorTTL   = 6 * time.Hour
	overviewTTL = 6 * time.Hour
	readModelV  = "v2.3"
	maxScanSyms = 80
	stopLossPct = -8.0
)

func toFactorBars(bars []mwinflux.KlineBar) []factor.Bar {
	out := make([]factor.Bar, len(bars))
	for i, b := range bars {
		out[i] = factor.Bar{Date: b.Date, Open: b.Open, High: b.High, Low: b.Low, Close: b.Close, Volume: b.Volume}
	}
	return out
}

func mustJSON(v any) string {
	raw, err := json.Marshal(v)
	if err != nil {
		return "{}"
	}
	return string(raw)
}

func (s *Service) putScheduled(ctx context.Context, kind string, payload any, ttl time.Duration) error {
	if s.rdb == nil {
		return nil
	}
	return s.rdb.Set(ctx, "readmodel:scheduled:"+kind, mustJSON(payload), ttl).Err()
}

func (s *Service) addReadmodel(ctx context.Context, kind, payload string) error {
	_, err := s.db.ExecContext(ctx, `
INSERT INTO quant_readmodel_snapshot (snapshot_type, payload_json, create_time)
VALUES (?, ?, NOW())`, kind, payload)
	return err
}

func (s *Service) latestReadmodel(ctx context.Context, kind string) map[string]any {
	var raw string
	err := s.db.QueryRowContext(ctx, `
SELECT payload_json FROM quant_readmodel_snapshot
WHERE snapshot_type = ? ORDER BY create_time DESC LIMIT 1`, kind).Scan(&raw)
	if err != nil || raw == "" {
		return map[string]any{}
	}
	var out map[string]any
	if json.Unmarshal([]byte(raw), &out) != nil {
		return map[string]any{}
	}
	return out
}

type symbolMarket struct {
	symbol string
	market string
}

func (s *Service) prefetchKlines(ctx context.Context, items []symbolMarket, start string, limit int) (map[string][]mwinflux.KlineBar, []string) {
	byMarket := map[string][]string{}
	for _, it := range items {
		byMarket[it.market] = append(byMarket[it.market], it.symbol)
	}
	out := map[string][]mwinflux.KlineBar{}
	var failedMarkets []string
	for market, symbols := range byMarket {
		fetched, err := s.reader.QueryKlinesMany(ctx, market, unique(symbols), start, limit)
		if err != nil {
			failedMarkets = append(failedMarkets, market)
			continue
		}
		for _, sym := range unique(symbols) {
			out[sym+"|"+market] = fetched[sym]
		}
	}
	return out, failedMarkets
}

func unique(xs []string) []string {
	seen := map[string]bool{}
	out := []string{}
	for _, x := range xs {
		if x == "" || seen[x] {
			continue
		}
		seen[x] = true
		out = append(out, x)
	}
	return out
}

func payloadString(payload map[string]any, keys ...string) string {
	for _, k := range keys {
		if v, ok := payload[k]; ok && v != nil {
			s := strings.TrimSpace(fmt.Sprint(v))
			if s != "" && s != "<nil>" {
				return s
			}
		}
	}
	return ""
}

func payloadInt(payload map[string]any, key string) int {
	v, ok := payload[key]
	if !ok || v == nil {
		return 0
	}
	switch x := v.(type) {
	case float64:
		return int(x)
	case int:
		return x
	case json.Number:
		n, _ := x.Int64()
		return int(n)
	case string:
		var n int
		_, _ = fmt.Sscan(x, &n)
		return n
	}
	return 0
}

func payloadSymbols(payload map[string]any) []string {
	raw, ok := payload["symbols"]
	if !ok || raw == nil {
		return nil
	}
	switch xs := raw.(type) {
	case []any:
		out := []string{}
		for _, v := range xs {
			s := strings.TrimSpace(strings.ToUpper(fmt.Sprint(v)))
			if s != "" && s != "<NIL>" {
				out = append(out, s)
			}
		}
		return out
	case []string:
		return xs
	}
	return nil
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}

func validProfile(p string) bool {
	switch p {
	case "conservative", "balanced", "aggressive":
		return true
	}
	return false
}
