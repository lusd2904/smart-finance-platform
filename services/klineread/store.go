package klineread

import "context"

// Store is the kline bar source. Production is MySQL; tests use MemStore.
// GetKlineSeries callers must not fall back to Influx when this returns empty.
type Store interface {
	QueryDaily(ctx context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error)
	QueryMinute(ctx context.Context, market, symbol, start, stop string, limit *int) ([]Bar, error)
	QueryDailyMany(ctx context.Context, market string, symbols []string, start string, limit int) (map[string][]Bar, error)
	LatestDailyDate(ctx context.Context, market, symbol string) (string, error)
}
