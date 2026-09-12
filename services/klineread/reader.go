package klineread

import (
	"context"
	"database/sql"
	"log/slog"
	"strconv"
)

// Reader is the shared MySQL kline facade used by HTTP APIs and workers.
type Reader struct {
	Store Store
}

func NewSQL(db *sql.DB) *Reader {
	return &Reader{Store: &SQLStore{DB: db}}
}

func New(store Store) *Reader {
	return &Reader{Store: store}
}

func (r *Reader) QueryDaily(ctx context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error) {
	if r == nil || r.Store == nil {
		logEmpty("daily", market, symbol, start, stop, 0)
		return []Bar{}, nil
	}
	bars, err := r.Store.QueryDaily(ctx, market, symbol, start, stop, limit)
	if err != nil {
		return nil, err
	}
	if len(bars) == 0 {
		logEmpty("daily", market, symbol, start, stop, 0)
		return []Bar{}, nil
	}
	return bars, nil
}

func (r *Reader) QueryMinute(ctx context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error) {
	if r == nil || r.Store == nil {
		logEmpty("minute", market, symbol, start, stop, 0)
		return []Bar{}, nil
	}
	bars, err := r.Store.QueryMinute(ctx, market, symbol, start, stop, limit)
	if err != nil {
		return nil, err
	}
	if len(bars) == 0 {
		logEmpty("minute", market, symbol, start, stop, 0)
		return []Bar{}, nil
	}
	return bars, nil
}

func (r *Reader) QueryDailyMany(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]Bar, error) {
	if r == nil || r.Store == nil {
		return map[string][]Bar{}, nil
	}
	return r.Store.QueryDailyMany(ctx, market, symbols, start, limit)
}

func (r *Reader) QueryLatestDaily(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]Bar, error) {
	if n <= 0 {
		n = 2
	}
	if start == "" {
		start = "-60d"
	}
	return r.QueryDailyMany(ctx, market, symbols, start, n)
}

func (r *Reader) LatestDailyDate(ctx context.Context, market, symbol string) (string, error) {
	if r == nil || r.Store == nil {
		return "", nil
	}
	return r.Store.LatestDailyDate(ctx, market, symbol)
}

func (r *Reader) QueryDailyValues(ctx context.Context, market, symbol, start string, limit int) ([]ValueBar, error) {
	lim := limit
	bars, err := r.QueryDaily(ctx, market, symbol, start, "now()", &lim)
	if err != nil {
		return nil, err
	}
	return ToValueBars(bars), nil
}

func (r *Reader) QueryDailyManyValues(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]ValueBar, error) {
	grouped, err := r.QueryDailyMany(ctx, market, symbols, start, limit)
	if err != nil {
		return nil, err
	}
	return valueBarMap(grouped), nil
}

func (r *Reader) QueryLatestDailyValues(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]ValueBar, error) {
	grouped, err := r.QueryLatestDaily(ctx, market, symbols, n, start)
	if err != nil {
		return nil, err
	}
	return valueBarMap(grouped), nil
}

func (r *Reader) QueryMinuteValues(ctx context.Context, market, symbol, start, stop string, limit int) ([]ValueBar, error) {
	lim := limit
	bars, err := r.QueryMinute(ctx, market, symbol, start, stop, &lim)
	if err != nil {
		return nil, err
	}
	return ToValueBars(bars), nil
}

func logEmpty(table, market, symbol, start, stop string, n int) {
	slog.Info("kline mysql empty",
		"table", table, "market", market, "symbol", symbol,
		"start", start, "stop", stop, "rows", n)
}

// DailyPageRow is one opensync-style daily bar (string OHLC to match the old Flux CSV).
type DailyPageRow struct {
	Symbol string
	Market string
	Date   string
	Open   string
	High   string
	Low    string
	Close  string
	Volume string
}

func (s *SQLStore) QueryDailyPage(ctx context.Context, market, since string, pageSize, offset int) ([]DailyPageRow, error) {
	if s == nil || s.DB == nil {
		return nil, nil
	}
	if pageSize <= 0 {
		pageSize = 1000
	}
	if offset < 0 {
		offset = 0
	}
	query, args := dailyPageSQL(market, since, pageSize, offset)
	rows, err := s.DB.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := make([]DailyPageRow, 0)
	for rows.Next() {
		var symbol, mkt string
		var raw interface{}
		var open, high, low, close, volume sql.NullFloat64
		if err := rows.Scan(&symbol, &mkt, &raw, &open, &high, &low, &close, &volume); err != nil {
			return nil, err
		}
		out = append(out, DailyPageRow{
			Symbol: symbol,
			Market: mkt,
			Date:   coerceDate(raw),
			Open:   formatNullFloat(open),
			High:   formatNullFloat(high),
			Low:    formatNullFloat(low),
			Close:  formatNullFloat(close),
			Volume: formatNullFloat(volume),
		})
	}
	return out, rows.Err()
}

func formatNullFloat(v sql.NullFloat64) string {
	if !v.Valid {
		return ""
	}
	return strconv.FormatFloat(v.Float64, 'f', -1, 64)
}
