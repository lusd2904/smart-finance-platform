package influx

import (
	"context"
	"database/sql"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
)

type KlineBar = klineread.ValueBar

type Reader struct {
	src *klineread.Reader
}

func NewReader(db *sql.DB) *Reader {
	return &Reader{src: klineread.NewSQL(db)}
}

func NewReaderWithStore(store klineread.Store) *Reader {
	return &Reader{src: klineread.New(store)}
}

func (r *Reader) QueryLatestKlines(ctx context.Context, market string, symbols []string, n int, start string) (map[string][]KlineBar, error) {
	if r == nil || r.src == nil {
		return map[string][]KlineBar{}, nil
	}
	return r.src.QueryLatestDailyValues(ctx, market, symbols, n, start)
}

func (r *Reader) QueryKlinesMany(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]KlineBar, error) {
	if r == nil || r.src == nil {
		return map[string][]KlineBar{}, nil
	}
	if limit <= 0 {
		limit = 320
	}
	if start == "" {
		start = "-1y"
	}
	return r.src.QueryDailyManyValues(ctx, market, symbols, start, limit)
}

func (r *Reader) QueryKlines(ctx context.Context, market, symbol, start string, limit int) ([]KlineBar, error) {
	if r == nil || r.src == nil {
		return nil, nil
	}
	if limit <= 0 {
		limit = 8
	}
	return r.src.QueryDailyValues(ctx, market, symbol, start, limit)
}

func (r *Reader) QueryMinuteKlines(ctx context.Context, market, symbol, start, stop string, limit int) ([]KlineBar, error) {
	if r == nil || r.src == nil {
		return nil, nil
	}
	if stop == "" {
		stop = "now()"
	}
	return r.src.QueryMinuteValues(ctx, market, symbol, start, stop, limit)
}
