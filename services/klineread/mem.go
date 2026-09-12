package klineread

import (
	"context"
	"sort"
	"strings"
	"time"
)

// DailyRow is one persisted daily bar (matches market_price_history_daily).
type DailyRow struct {
	Symbol    string
	Market    string
	TradeDate string
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
}

// MinuteRow is one persisted minute bar (matches market_price_history_minute).
type MinuteRow struct {
	Symbol  string
	Market  string
	BarTime time.Time
	Open    float64
	High    float64
	Low     float64
	Close   float64
	Volume  float64
}

// MemStore is an in-memory upsert/read stand-in for MySQL.
type MemStore struct {
	Daily  map[string]DailyRow
	Minute map[string]MinuteRow
}

func NewMemStore() *MemStore {
	return &MemStore{
		Daily:  map[string]DailyRow{},
		Minute: map[string]MinuteRow{},
	}
}

func dailyKey(symbol, tradeDate string) string {
	return strings.ToUpper(strings.TrimSpace(symbol)) + "\x00" + strings.TrimSpace(tradeDate)
}

func minuteKey(symbol, market string, barTime time.Time) string {
	return strings.ToUpper(strings.TrimSpace(symbol)) + "\x00" +
		strings.ToUpper(strings.TrimSpace(market)) + "\x00" +
		barTime.Format("2006-01-02 15:04:05")
}

// UpsertDaily replaces the row for (symbol, trade_date), matching the MySQL unique key.
func (m *MemStore) UpsertDaily(row DailyRow) {
	if m.Daily == nil {
		m.Daily = map[string]DailyRow{}
	}
	row.Symbol = strings.TrimSpace(row.Symbol)
	row.Market = normalizeMarket(row.Market)
	row.TradeDate = strings.TrimSpace(row.TradeDate)
	m.Daily[dailyKey(row.Symbol, row.TradeDate)] = row
}

// UpsertMinute replaces the row for (symbol, market, bar_time).
func (m *MemStore) UpsertMinute(row MinuteRow) {
	if m.Minute == nil {
		m.Minute = map[string]MinuteRow{}
	}
	row.Symbol = strings.TrimSpace(row.Symbol)
	row.Market = normalizeMarket(row.Market)
	m.Minute[minuteKey(row.Symbol, row.Market, row.BarTime)] = row
}

func (m *MemStore) QueryDaily(_ context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error) {
	from, to, ok := resolveRange(start, stop, nowBeijing())
	if !ok {
		return []Bar{}, nil
	}
	startDate := formatDailyDate(from)
	endDate := formatDailyDate(to)
	mkt := normalizeMarket(market)
	var match []DailyRow
	for _, cand := range symbolLookupOrder(symbol) {
		match = m.dailyRows(mkt, cand, startDate, endDate)
		if len(match) > 0 {
			break
		}
	}
	sort.Slice(match, func(i, j int) bool { return match[i].TradeDate < match[j].TradeDate })
	bars := make([]Bar, 0, len(match))
	for _, row := range match {
		bars = append(bars, barFromValues(row.TradeDate, row.Open, row.High, row.Low, row.Close, row.Volume))
	}
	return lastNBars(bars, clampLimit(limit)), nil
}

func (m *MemStore) dailyRows(market, symbol, startDate, endDate string) []DailyRow {
	var out []DailyRow
	for _, row := range m.Daily {
		if row.Symbol != symbol || row.Market != market {
			continue
		}
		if row.TradeDate < startDate || row.TradeDate > endDate {
			continue
		}
		out = append(out, row)
	}
	return out
}

func (m *MemStore) QueryMinute(_ context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error) {
	from, to, ok := resolveRange(start, stop, nowBeijing())
	if !ok {
		return []Bar{}, nil
	}
	mkt := normalizeMarket(market)
	var match []MinuteRow
	for _, cand := range symbolLookupOrder(symbol) {
		match = m.minuteRows(mkt, cand, from, to)
		if len(match) > 0 {
			break
		}
	}
	sort.Slice(match, func(i, j int) bool { return match[i].BarTime.Before(match[j].BarTime) })
	bars := make([]Bar, 0, len(match))
	for _, row := range match {
		bars = append(bars, barFromValues(formatMinuteDate(row.BarTime), row.Open, row.High, row.Low, row.Close, row.Volume))
	}
	return lastNBars(bars, clampLimit(limit)), nil
}

func (m *MemStore) minuteRows(market, symbol string, from, to time.Time) []MinuteRow {
	var out []MinuteRow
	for _, row := range m.Minute {
		if row.Symbol != symbol || row.Market != market {
			continue
		}
		ts := row.BarTime
		if ts.Before(from) || ts.After(to) {
			continue
		}
		out = append(out, row)
	}
	return out
}

func (m *MemStore) QueryDailyMany(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]Bar, error) {
	out := map[string][]Bar{}
	lim := limit
	if lim <= 0 {
		lim = 320
	}
	for _, sym := range sanitizeSymbols(symbols) {
		bars, err := m.QueryDaily(ctx, market, sym, start, "now()", &lim)
		if err != nil {
			return nil, err
		}
		if len(bars) > 0 {
			out[sym] = bars
		}
	}
	return out, nil
}

func (m *MemStore) LatestDailyDate(ctx context.Context, market, symbol string) (string, error) {
	lim := 1
	bars, err := m.QueryDaily(ctx, market, symbol, "-20y", "now()", &lim)
	if err != nil || len(bars) == 0 {
		return "", err
	}
	return bars[len(bars)-1].Date, nil
}
