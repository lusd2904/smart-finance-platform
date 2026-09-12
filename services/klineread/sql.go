package klineread

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"
)

const (
	dailySelectCols  = `trade_date, open_price, high_price, low_price, close_price, volume`
	minuteSelectCols = `bar_time, open_price, high_price, low_price, close_price, volume`
)

// SQLStore reads daily/minute bars from MySQL. Empty results are not an error.
type SQLStore struct {
	DB *sql.DB
}

func (s *SQLStore) QueryDaily(ctx context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error) {
	if s == nil || s.DB == nil {
		return []Bar{}, nil
	}
	from, to, ok := resolveRange(start, stop, nowBeijing())
	if !ok {
		return []Bar{}, nil
	}
	mkt := normalizeMarket(market)
	startDate := formatDailyDate(from)
	endDate := formatDailyDate(to)
	lim := clampLimit(limit)
	for _, cand := range symbolLookupOrder(symbol) {
		bars, err := s.queryDailyExact(ctx, mkt, cand, startDate, endDate, lim)
		if err != nil {
			return nil, err
		}
		if len(bars) > 0 {
			return bars, nil
		}
	}
	return []Bar{}, nil
}

func (s *SQLStore) queryDailyExact(ctx context.Context, market, symbol, startDate, endDate string, limit int) ([]Bar, error) {
	query := fmt.Sprintf(`SELECT %s FROM market_price_history_daily
WHERE symbol=? AND market=? AND trade_date>=? AND trade_date<=?
ORDER BY trade_date`, dailySelectCols)
	args := []interface{}{symbol, market, startDate, endDate}
	if limit > 0 {
		query = fmt.Sprintf(`SELECT %s FROM (
SELECT %s FROM market_price_history_daily
WHERE symbol=? AND market=? AND trade_date>=? AND trade_date<=?
ORDER BY trade_date DESC
LIMIT ?
) t ORDER BY trade_date`, dailySelectCols, dailySelectCols)
		args = append(args, limit)
	}
	rows, err := s.DB.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanDailyRows(rows)
}

func (s *SQLStore) QueryMinute(ctx context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error) {
	if s == nil || s.DB == nil {
		return []Bar{}, nil
	}
	from, to, ok := resolveRange(start, stop, nowBeijing())
	if !ok {
		return []Bar{}, nil
	}
	mkt := normalizeMarket(market)
	startAt := formatMinuteSQL(from)
	stopAt := formatMinuteSQL(to)
	lim := clampLimit(limit)
	for _, cand := range symbolLookupOrder(symbol) {
		bars, err := s.queryMinuteExact(ctx, mkt, cand, startAt, stopAt, lim)
		if err != nil {
			return nil, err
		}
		if len(bars) > 0 {
			return bars, nil
		}
	}
	return []Bar{}, nil
}

func (s *SQLStore) queryMinuteExact(ctx context.Context, market, symbol, startAt, stopAt string, limit int) ([]Bar, error) {
	query := fmt.Sprintf(`SELECT %s FROM market_price_history_minute
WHERE symbol=? AND market=? AND bar_time>=? AND bar_time<=?
ORDER BY bar_time`, minuteSelectCols)
	args := []interface{}{symbol, market, startAt, stopAt}
	if limit > 0 {
		query = fmt.Sprintf(`SELECT %s FROM (
SELECT %s FROM market_price_history_minute
WHERE symbol=? AND market=? AND bar_time>=? AND bar_time<=?
ORDER BY bar_time DESC
LIMIT ?
) t ORDER BY bar_time`, minuteSelectCols, minuteSelectCols)
		args = append(args, limit)
	}
	rows, err := s.DB.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	return scanMinuteRows(rows)
}

func (s *SQLStore) QueryDailyMany(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]Bar, error) {
	out := map[string][]Bar{}
	safe := sanitizeSymbols(symbols)
	if len(safe) == 0 {
		return out, nil
	}
	if limit <= 0 {
		limit = 320
	}
	const chunk = 30
	for i := 0; i < len(safe); i += chunk {
		end := i + chunk
		if end > len(safe) {
			end = len(safe)
		}
		part, err := s.queryDailyChunk(ctx, market, safe[i:end], start, limit)
		if err != nil {
			return nil, err
		}
		for sym, bars := range part {
			out[sym] = bars
		}
	}
	return out, nil
}

func (s *SQLStore) queryDailyChunk(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]Bar, error) {
	out := map[string][]Bar{}
	for _, sym := range symbols {
		lim := limit
		bars, err := s.QueryDaily(ctx, market, sym, start, "now()", &lim)
		if err != nil {
			return nil, err
		}
		if len(bars) > 0 {
			out[sym] = bars
		}
	}
	return out, nil
}

func (s *SQLStore) LatestDailyDate(ctx context.Context, market, symbol string) (string, error) {
	if s == nil || s.DB == nil {
		return "", nil
	}
	mkt := normalizeMarket(market)
	for _, cand := range symbolLookupOrder(symbol) {
		var tradeDate string
		err := s.DB.QueryRowContext(ctx, `
SELECT trade_date FROM market_price_history_daily
WHERE symbol=? AND market=?
ORDER BY trade_date DESC LIMIT 1`, cand, mkt).Scan(&tradeDate)
		if err == sql.ErrNoRows {
			continue
		}
		if err != nil {
			return "", err
		}
		if len(tradeDate) >= 10 {
			return tradeDate[:10], nil
		}
		if tradeDate != "" {
			return tradeDate, nil
		}
	}
	return "", nil
}

func scanDailyRows(rows *sql.Rows) ([]Bar, error) {
	out := make([]Bar, 0)
	for rows.Next() {
		var raw interface{}
		var open, high, low, close, volume sql.NullFloat64
		if err := rows.Scan(&raw, &open, &high, &low, &close, &volume); err != nil {
			return nil, err
		}
		tradeDate := coerceDate(raw)
		out = append(out, nullBar(tradeDate, open, high, low, close, volume))
	}
	return out, rows.Err()
}

func scanMinuteRows(rows *sql.Rows) ([]Bar, error) {
	out := make([]Bar, 0)
	for rows.Next() {
		var raw interface{}
		var open, high, low, close, volume sql.NullFloat64
		if err := rows.Scan(&raw, &open, &high, &low, &close, &volume); err != nil {
			return nil, err
		}
		out = append(out, nullBar(coerceMinute(raw), open, high, low, close, volume))
	}
	return out, rows.Err()
}

func coerceDate(v interface{}) string {
	switch t := v.(type) {
	case time.Time:
		return formatDailyDate(t)
	case []byte:
		s := strings.TrimSpace(string(t))
		if len(s) >= 10 {
			return s[:10]
		}
		return s
	case string:
		s := strings.TrimSpace(t)
		if len(s) >= 10 {
			return s[:10]
		}
		return s
	default:
		return ""
	}
}

func coerceMinute(v interface{}) string {
	switch t := v.(type) {
	case time.Time:
		return formatMinuteDate(t)
	case []byte:
		if parsed, ok := parseBound(string(t), nowBeijing()); ok {
			return formatMinuteDate(parsed)
		}
		s := strings.TrimSpace(string(t))
		if len(s) >= 16 {
			return s[:16]
		}
		return s
	case string:
		if parsed, ok := parseBound(t, nowBeijing()); ok {
			return formatMinuteDate(parsed)
		}
		s := strings.TrimSpace(t)
		if len(s) >= 16 {
			return s[:16]
		}
		return s
	default:
		return ""
	}
}

func nullBar(date string, open, high, low, close, volume sql.NullFloat64) Bar {
	b := Bar{Date: date}
	if open.Valid {
		b.Open = &open.Float64
	}
	if high.Valid {
		b.High = &high.Float64
	}
	if low.Valid {
		b.Low = &low.Float64
	}
	if close.Valid {
		b.Close = &close.Float64
	}
	if volume.Valid {
		b.Volume = &volume.Float64
	}
	return b
}

func dailyPageSQL(market, since string, pageSize, offset int) (string, []interface{}) {
	var b strings.Builder
	b.WriteString(`SELECT symbol, market, trade_date, open_price, high_price, low_price, close_price, volume
FROM market_price_history_daily WHERE market=?`)
	args := []interface{}{normalizeMarket(market)}
	if since != "" {
		b.WriteString(` AND trade_date>=?`)
		args = append(args, since)
	}
	b.WriteString(` ORDER BY trade_date, symbol LIMIT ? OFFSET ?`)
	args = append(args, pageSize, offset)
	return b.String(), args
}
