package cache

import (
	"context"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/redis/go-redis/v9"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/config"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/heat"
)

const (
	BoardQuotesKey = "sfp:cache:board:quotes"
	IndexQuotesKey = "market:index:quotes:v3"
	ScheduledBoard = "readmodel:scheduled:board"
)

type Cache struct {
	rdb *redis.Client
}

func New(cfg *config.Config) *Cache {
	return &Cache{rdb: redis.NewClient(&redis.Options{
		Addr:     fmt.Sprintf("%s:%d", cfg.RedisHost, cfg.RedisPort),
		Password: cfg.RedisPassword,
		DB:       cfg.RedisDB,
	})}
}

func (c *Cache) Ping(ctx context.Context) error { return c.rdb.Ping(ctx).Err() }
func (c *Cache) Close() error                   { return c.rdb.Close() }
func (c *Cache) Client() *redis.Client          { return c.rdb }

func (c *Cache) GetJSON(ctx context.Context, key string) (map[string]interface{}, error) {
	raw, err := c.rdb.Get(ctx, key).Result()
	if err != nil {
		return nil, err
	}
	var out map[string]interface{}
	if err := json.Unmarshal([]byte(raw), &out); err != nil {
		return nil, err
	}
	return out, nil
}

func (c *Cache) SetJSON(ctx context.Context, key string, value interface{}, ttlSeconds int) error {
	raw, err := json.Marshal(value)
	if err != nil {
		return err
	}
	ttl := time.Duration(ttlSeconds) * time.Second
	if ttlSeconds <= 0 {
		ttl = 0
	}
	return c.rdb.Set(ctx, key, raw, ttl).Err()
}

func (c *Cache) ResolveHeatWeights(ctx context.Context) map[string]float64 {
	weights := map[string]float64{}
	for k, v := range heat.DefaultWeights {
		weights[k] = v
	}
	for configKey, field := range heat.WeightConfigKeys {
		raw, err := c.rdb.Get(ctx, "sys_config:"+configKey).Result()
		if err != nil || strings.TrimSpace(raw) == "" {
			continue
		}
		if f, err := strconv.ParseFloat(raw, 64); err == nil {
			weights[field] = f
		}
	}
	total := 0.0
	for _, v := range weights {
		total += v
	}
	if total <= 0 {
		total = 1
	}
	norm := map[string]float64{}
	for k, v := range weights {
		norm[k] = round4(v / total)
	}
	return norm
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}

func QuoteLastPrice(quote map[string]interface{}) *float64 {
	for _, key := range []string{"lastDone", "last", "close", "price"} {
		if v, ok := quote[key]; ok && v != nil && v != "" {
			switch n := v.(type) {
			case float64:
				return &n
			case json.Number:
				if f, err := n.Float64(); err == nil {
					return &f
				}
			}
		}
	}
	return nil
}

func EnrichTop50Last(top50 []map[string]interface{}, board map[string]interface{}, market string) {
	if len(top50) == 0 || board == nil {
		return
	}
	quotes, _ := board["quotes"].([]interface{})
	if quotes == nil {
		quotes, _ = board["rows"].([]interface{})
	}
	bySymbol := map[string]float64{}
	marketU := strings.ToUpper(market)
	for _, item := range quotes {
		q, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		qm := strings.ToUpper(fmt.Sprint(q["market"]))
		if qm != "" && qm != marketU {
			continue
		}
		sym := strings.ToUpper(fmt.Sprint(q["symbol"]))
		if sym == "" {
			continue
		}
		if last := QuoteLastPrice(q); last != nil {
			bySymbol[sym] = *last
		}
	}
	for _, item := range top50 {
		if item["last"] != nil {
			continue
		}
		sym := strings.ToUpper(fmt.Sprint(item["symbol"]))
		if last, ok := bySymbol[sym]; ok {
			item["last"] = last
		}
	}
}

func FilterBoardPayload(payload map[string]interface{}, category, market string) map[string]interface{} {
	quotes := toQuoteMaps(payload["quotes"])
	if quotes == nil {
		quotes = toQuoteMaps(payload["rows"])
	}
	if market != "" {
		mkt := strings.ToUpper(strings.TrimSpace(market))
		filtered := make([]map[string]interface{}, 0)
		for _, q := range quotes {
			if strings.ToUpper(fmt.Sprint(q["market"])) == mkt {
				filtered = append(filtered, q)
			}
		}
		quotes = filtered
	}
	if category != "" {
		cat := strings.TrimSpace(category)
		filtered := make([]map[string]interface{}, 0)
		for _, q := range quotes {
			if fmt.Sprint(q["category"]) == cat {
				filtered = append(filtered, q)
			}
		}
		quotes = filtered
	}
	indices := make([]map[string]interface{}, 0)
	indexSymbols := map[string]bool{}
	for _, q := range quotes {
		sym := fmt.Sprint(q["symbol"])
		if fmt.Sprint(q["category"]) == "index" || strings.HasPrefix(sym, "^") {
			indices = append(indices, q)
			indexSymbols[sym] = true
		}
	}
	rows := make([]map[string]interface{}, 0)
	for _, q := range quotes {
		sym := fmt.Sprint(q["symbol"])
		if !indexSymbols[sym] {
			rows = append(rows, q)
		}
	}
	out := map[string]interface{}{}
	for k, v := range payload {
		out[k] = v
	}
	out["quotes"] = quotes
	out["indices"] = indices
	out["rows"] = rows
	out["count"] = len(quotes)
	return out
}

func AdaptScheduledBoard(scheduled map[string]interface{}) map[string]interface{} {
	items, _ := scheduled["items"].([]interface{})
	quotes := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		row, ok := item.(map[string]interface{})
		if !ok {
			continue
		}
		changeRate := row["changeRate"]
		price := row["close"]
		if price == nil {
			price = row["price"]
		}
		changeText := "--"
		if cr, ok := changeRate.(float64); ok {
			sign := "+"
			if cr < 0 {
				sign = ""
			}
			changeText = fmt.Sprintf("%s%.2f%%", sign, cr)
		}
		up := true
		if cr, ok := changeRate.(float64); ok {
			up = cr >= 0
		}
		quotes = append(quotes, map[string]interface{}{
			"symbol":     row["symbol"],
			"name":       row["name"],
			"market":     row["market"],
			"category":   row["category"],
			"price":      price,
			"change":     row["change"],
			"changeRate": changeRate,
			"volume":     row["volume"],
			"tradeDate":  firstNonNil(row["asOf"], row["tradeDate"]),
			"changeText": changeText,
			"up":         up,
			"source":     "scheduled",
		})
	}
	return map[string]interface{}{
		"quotes": quotes,
		"asOf":   scheduled["asOf"],
		"source": "scheduled",
	}
}

func toQuoteMaps(v interface{}) []map[string]interface{} {
	items, ok := v.([]interface{})
	if !ok {
		return nil
	}
	out := make([]map[string]interface{}, 0, len(items))
	for _, item := range items {
		if m, ok := item.(map[string]interface{}); ok {
			out = append(out, m)
		}
	}
	return out
}

func firstNonNil(a, b interface{}) interface{} {
	if a != nil {
		return a
	}
	return b
}
