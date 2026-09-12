package store

import (
	"context"
	"log/slog"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
)

// insertDailySQL upserts one bar per (symbol, trade_date).
// Readers use this table; Influx write is still the dual-write companion.
const insertDailySQL = `INSERT INTO market_price_history_daily
(symbol, market, trade_date, open_price, high_price, low_price, close_price, volume, turnover, source, update_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NOW())
ON DUPLICATE KEY UPDATE
market=VALUES(market), open_price=VALUES(open_price), high_price=VALUES(high_price),
low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume),
source=VALUES(source), update_time=VALUES(update_time)`

type dailyInfluxWriter interface {
	WriteDaily(ctx context.Context, market string, rows []influx.Bar) (int, error)
}

func upsertDailyBars(ctx context.Context, db dbExecer, rows []kline.Row) (int, error) {
	if len(rows) == 0 {
		return 0, nil
	}
	n := 0
	var firstErr error
	for _, r := range rows {
		if strings.TrimSpace(r.Symbol) == "" || strings.TrimSpace(r.TradeDate) == "" {
			continue
		}
		source := strings.TrimSpace(r.Source)
		if source == "" {
			source = "sina"
		}
		_, err := db.ExecContext(ctx, insertDailySQL,
			r.Symbol, r.Market, r.TradeDate,
			r.Open, r.High, r.Low, r.Close, r.Volume, source)
		if err != nil {
			if firstErr == nil {
				firstErr = err
			}
			continue
		}
		n++
	}
	return n, firstErr
}

// writeDailyDual upserts daily bars to MySQL (source of truth for reads), then
// best-effort WriteDaily to Influx when w is non-nil. Influx errors are logged
// and do not fail the job. MySQL upsert errors fail the job.
func writeDailyDual(ctx context.Context, w dailyInfluxWriter, db dbExecer, market string, rows []kline.Row) (int, error) {
	n, mysqlErr := upsertDailyBars(ctx, db, rows)
	if w != nil {
		if _, influxErr := w.WriteDaily(ctx, market, toInfluxBars(rows)); influxErr != nil {
			slog.Error("daily dual-write: influx write failed; mysql is source of truth",
				"market", market, "bars", len(rows), "err", influxErr)
		}
	}
	if mysqlErr != nil {
		return n, mysqlErr
	}
	return n, nil
}

func toInfluxBars(rows []kline.Row) []influx.Bar {
	out := make([]influx.Bar, 0, len(rows))
	for _, r := range rows {
		ts, err := influx.ParseDate(r.TradeDate)
		if err != nil {
			continue
		}
		out = append(out, influx.Bar{
			Symbol: r.Symbol, TradeDate: ts,
			Open: r.Open, High: r.High, Low: r.Low, Close: r.Close, Volume: r.Volume,
		})
	}
	return out
}
