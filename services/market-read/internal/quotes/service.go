package quotes

import (
	"context"
	"crypto/sha1"
	"encoding/hex"
	"log"
	"strings"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/cache"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/tencent"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/timeutil"
)

const (
	IndexTTLSeconds = 30
	LiveTTLSeconds  = 5
	LiveCachePrefix = "market:live:quotes:"
	fetchChunk      = 40
)

// Fetcher is the Tencent (or test double) batch quote source.
type Fetcher interface {
	FetchBatch(ctx context.Context, codes []string) (map[string]tencent.Quote, error)
}

type Service struct {
	Cache   *cache.Cache
	Fetcher Fetcher
}

var indexSpecs = []struct {
	Code   string
	Name   string
	Market string
}{
	{"usINX", "标普500", "US"},
	{"usIXIC", "纳斯达克", "US"},
	{"usDJI", "道琼斯", "US"},
	{"r_hkHSI", "恒生指数", "HK"},
	{"r_hkHSTECH", "恒生科技", "HK"},
	{"r_hkHSCEI", "恒生国企", "HK"},
	{"sh000001", "上证指数", "CN"},
	{"sz399006", "创业板指数", "CN"},
	{"sh000688", "科创板指数", "CN"},
}

// IndexQuotes returns the FE index-bar payload (same shape as Python MarketIndexService).
func (s *Service) IndexQuotes(ctx context.Context) map[string]interface{} {
	if s.Cache != nil {
		if cached, err := s.Cache.GetJSON(ctx, cache.IndexQuotesKey); err == nil && cached != nil {
			cached["cached"] = true
			return cached
		}
	}
	items := s.fetchIndexItems(ctx)
	payload := map[string]interface{}{
		"items": items,
		"asOf":  timeutil.NowBeijingRFC(),
	}
	if s.Cache != nil && len(items) > 0 {
		_ = s.Cache.SetJSON(ctx, cache.IndexQuotesKey, payload, IndexTTLSeconds)
	}
	out := map[string]interface{}{
		"items":  items,
		"asOf":   payload["asOf"],
		"cached": false,
	}
	return out
}

func (s *Service) fetchIndexItems(ctx context.Context) []map[string]interface{} {
	if s.Fetcher == nil {
		return []map[string]interface{}{}
	}
	codes := make([]string, 0, len(indexSpecs))
	for _, spec := range indexSpecs {
		codes = append(codes, spec.Code)
	}
	quotes, err := s.Fetcher.FetchBatch(ctx, codes)
	if err != nil {
		log.Printf("index-quotes: batch failed: %v", err)
		return []map[string]interface{}{}
	}
	items := make([]map[string]interface{}, 0, len(indexSpecs))
	for _, spec := range indexSpecs {
		quote, ok := quotes[spec.Code]
		if !ok || quote.Last == nil {
			continue
		}
		changePct := quote.ChangePct
		if changePct == nil && quote.Last != nil && quote.PrevClose != nil && *quote.PrevClose != 0 {
			v := round2((*quote.Last / *quote.PrevClose - 1.0) * 100)
			changePct = &v
		}
		items = append(items, map[string]interface{}{
			"market":    spec.Market,
			"symbol":    spec.Code,
			"name":      spec.Name,
			"last":      *quote.Last,
			"prevClose": nullFloat(quote.PrevClose),
			"changePct": nullFloat(changePct),
			"quoteTime": quote.QuoteTime,
		})
	}
	return items
}

// LiveQuotes returns the FE quotes snapshot (Tencent + Redis 5s cache).
// Longbridge push stays on Python until P1; this is the same fallback Python uses
// when QuoteContext is unavailable.
func (s *Service) LiveQuotes(ctx context.Context, pairs []Pair) map[string]interface{} {
	normalized := make([]Pair, 0, len(pairs))
	seen := map[string]bool{}
	for _, pair := range pairs {
		p, ok := NormalizeSymbolMarket(pair.Symbol, pair.Market)
		if !ok || seen[p.Key()] {
			continue
		}
		seen[p.Key()] = true
		normalized = append(normalized, p)
		if len(normalized) >= MaxLiveSymbols {
			break
		}
	}
	if len(normalized) == 0 {
		return map[string]interface{}{
			"items":  []interface{}{},
			"asOf":   timeutil.NowBeijingRFC(),
			"source": "empty",
			"cached": false,
		}
	}
	cacheKey := LiveCachePrefix + liveCacheHash(normalized)
	if s.Cache != nil {
		if cached, err := s.Cache.GetJSON(ctx, cacheKey); err == nil && cached != nil {
			if _, ok := cached["items"]; ok {
				cached["cached"] = true
				return cached
			}
		}
	}
	items := s.fetchLiveItems(ctx, normalized)
	payload := map[string]interface{}{
		"items":  items,
		"asOf":   timeutil.NowBeijingRFC(),
		"source": payloadSource(items),
	}
	if s.Cache != nil && len(items) > 0 {
		_ = s.Cache.SetJSON(ctx, cacheKey, payload, LiveTTLSeconds)
	}
	payload["cached"] = false
	return payload
}

func (s *Service) fetchLiveItems(ctx context.Context, pairs []Pair) []map[string]interface{} {
	if s.Fetcher == nil {
		return []map[string]interface{}{}
	}
	codeMap := map[string]Pair{}
	codes := make([]string, 0, len(pairs))
	for _, pair := range pairs {
		code := tencent.Symbol(pair.Symbol, pair.Market)
		if code == "" || codeMap[code].Symbol != "" {
			continue
		}
		codeMap[code] = pair
		codes = append(codes, code)
	}
	quotes := map[string]tencent.Quote{}
	for i := 0; i < len(codes); i += fetchChunk {
		end := i + fetchChunk
		if end > len(codes) {
			end = len(codes)
		}
		chunk, err := s.Fetcher.FetchBatch(ctx, codes[i:end])
		if err != nil {
			log.Printf("live-quotes: tencent batch failed n=%d: %v", end-i, err)
			continue
		}
		for k, v := range chunk {
			quotes[k] = v
		}
	}
	items := make([]map[string]interface{}, 0, len(pairs))
	for _, pair := range pairs {
		code := tencent.Symbol(pair.Symbol, pair.Market)
		quote, ok := quotes[code]
		if !ok || quote.Last == nil {
			continue
		}
		changePct := quote.ChangePct
		if changePct == nil && quote.PrevClose != nil && *quote.PrevClose != 0 {
			v := round2((*quote.Last / *quote.PrevClose - 1.0) * 100)
			changePct = &v
		}
		name := quote.Name
		if name == "" {
			name = pair.Symbol
		}
		items = append(items, map[string]interface{}{
			"symbol":     pair.Symbol,
			"market":     pair.Market,
			"name":       name,
			"last":       *quote.Last,
			"prevClose":  nullFloat(quote.PrevClose),
			"changePct":  nullFloat(changePct),
			"changeRate": nullFloat(changePct),
			"quoteTime":  quote.QuoteTime,
			"source":     "tencent",
		})
	}
	return items
}

func liveCacheHash(pairs []Pair) string {
	parts := make([]string, 0, len(pairs))
	for _, p := range pairs {
		parts = append(parts, p.Market+":"+p.Symbol)
	}
	sum := sha1.Sum([]byte(strings.Join(parts, ",")))
	return hex.EncodeToString(sum[:])[:16]
}

func payloadSource(items []map[string]interface{}) string {
	if len(items) == 0 {
		return "tencent"
	}
	return "tencent"
}

func round2(v float64) float64 {
	return float64(int(v*100+0.5)) / 100
}

func nullFloat(v *float64) interface{} {
	if v == nil {
		return nil
	}
	return *v
}
