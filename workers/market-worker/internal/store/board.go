package store

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/cache"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/influx"
)

type instrumentRow struct {
	Symbol   string
	Name     string
	Market   string
	Category string
}

func (s *Service) RefreshBoardQuotesCache(ctx context.Context) (map[string]interface{}, error) {
	instruments, err := s.listAllInstruments(ctx)
	if err != nil {
		return nil, err
	}
	byMarket := map[string][]string{}
	for _, inst := range instruments {
		if inst.Symbol == "" {
			continue
		}
		mkt := strings.ToUpper(inst.Market)
		if mkt == "" {
			mkt = "US"
		}
		byMarket[mkt] = append(byMarket[mkt], inst.Symbol)
	}

	barsBySymbol := map[string][]influx.KlineBar{}
	for mkt, symbols := range byMarket {
		grouped, err := s.reader.QueryLatestKlines(ctx, mkt, symbols, 2, "-60d")
		if err != nil {
			continue
		}
		for sym, bars := range grouped {
			barsBySymbol[sym] = bars
		}
	}

	quotes := make([]map[string]interface{}, 0, len(instruments))
	for _, inst := range instruments {
		bars := barsBySymbol[inst.Symbol]
		quote := buildQuoteFromKlines(bars)
		source := "none"
		if len(bars) > 0 {
			source = "influx"
		}
		last := quote["last"]
		changeRate := quote["changeRate"]
		changeText := "--"
		up := true
		if rate, ok := changeRate.(float64); ok {
			changeText = fmt.Sprintf("%+.2f%%", rate)
			up = rate >= 0
		}
		mkt := strings.ToUpper(inst.Market)
		if mkt == "" {
			mkt = "US"
		}
		quotes = append(quotes, map[string]interface{}{
			"symbol":     inst.Symbol,
			"name":       inst.Name,
			"market":     mkt,
			"category":   inst.Category,
			"price":      last,
			"open":       quote["open"],
			"high":       quote["high"],
			"low":        quote["low"],
			"volume":     quote["volume"],
			"change":     quote["change"],
			"changeRate": changeRate,
			"prevClose":  quote["prevClose"],
			"tradeDate":  quote["tradeDate"],
			"changeText": changeText,
			"up":         up,
			"source":     source,
			"bars":       len(bars),
		})
	}

	indices := []map[string]interface{}{}
	indexSymbols := map[string]bool{}
	for _, q := range quotes {
		cat, _ := q["category"].(string)
		sym, _ := q["symbol"].(string)
		if cat == "index" || strings.HasPrefix(sym, "^") {
			indices = append(indices, q)
			indexSymbols[sym] = true
		}
	}
	rows := []map[string]interface{}{}
	for _, q := range quotes {
		sym, _ := q["symbol"].(string)
		if !indexSymbols[sym] {
			rows = append(rows, q)
		}
	}
	asOf := beijingNow()
	payload := map[string]interface{}{
		"quotes":  quotes,
		"indices": indices,
		"rows":    rows,
		"source":  "cache",
		"count":   len(quotes),
		"asOf":    asOf,
		"stale":   false,
	}
	if err := cache.SetJSON(ctx, s.rdb, cache.BoardQuotesKey, payload, cache.BoardQuotesTTL); err != nil {
		return nil, err
	}
	return map[string]interface{}{"count": len(quotes), "asOf": asOf}, nil
}

func (s *Service) listAllInstruments(ctx context.Context) ([]instrumentRow, error) {
	rows, err := s.db.QueryContext(ctx, `
SELECT symbol, name, market, category
FROM market_instrument
WHERE enabled='1'
ORDER BY FIELD(market, 'US','HK','CN'), symbol`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []instrumentRow
	for rows.Next() {
		var inst instrumentRow
		if err := rows.Scan(&inst.Symbol, &inst.Name, &inst.Market, &inst.Category); err != nil {
			continue
		}
		out = append(out, inst)
	}
	return out, nil
}

func buildQuoteFromKlines(bars []influx.KlineBar) map[string]interface{} {
	if len(bars) == 0 {
		return map[string]interface{}{}
	}
	last := bars[len(bars)-1]
	var prev *influx.KlineBar
	if len(bars) > 1 {
		p := bars[len(bars)-2]
		prev = &p
	}
	var change, changeRate interface{}
	if prev != nil && prev.Close > 0 && last.Close > 0 {
		chg := last.Close - prev.Close
		change = round4(chg)
		changeRate = round4(chg / prev.Close * 100)
	}
	prevClose := interface{}(nil)
	if prev != nil {
		prevClose = prev.Close
	}
	return map[string]interface{}{
		"last":       last.Close,
		"open":       last.Open,
		"high":       last.High,
		"low":        last.Low,
		"volume":     last.Volume,
		"tradeDate":  last.Date,
		"change":     change,
		"changeRate": changeRate,
		"prevClose":  prevClose,
	}
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}

func beijingNow() string {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		return time.Now().Format("2006-01-02 15:04:05")
	}
	return time.Now().In(loc).Format("2006-01-02 15:04:05")
}
