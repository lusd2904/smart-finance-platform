package store

import (
	"context"
	"database/sql"
	"log/slog"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
)

// insertMinuteSQL upserts one bar per (symbol, market, bar_time).
// Phase 1 dual-write: readers stay on Influx; Influx is removed only after a later reader cutover.
const insertMinuteSQL = `INSERT INTO market_price_history_minute
(symbol, market, trade_date, bar_time, open_price, high_price, low_price, close_price, volume, source, update_time)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
ON DUPLICATE KEY UPDATE
open_price=VALUES(open_price), high_price=VALUES(high_price),
low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume),
source=VALUES(source), update_time=VALUES(update_time)`

type dbExecer interface {
	ExecContext(ctx context.Context, query string, args ...interface{}) (sql.Result, error)
}

type minuteInfluxWriter interface {
	WriteMinute(ctx context.Context, market string, rows []influx.Bar) (int, error)
}

func minuteBarsFromRows(rows []kline.Row) []influx.Bar {
	out := make([]influx.Bar, 0, len(rows))
	for _, r := range rows {
		ts, err := influx.ParseMinute(r.TradeDate)
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

func minuteSource(rows []kline.Row) string {
	for _, r := range rows {
		if s := strings.TrimSpace(r.Source); s != "" {
			return s
		}
	}
	return "tencent"
}

func upsertMinuteBars(ctx context.Context, db dbExecer, market, source string, bars []influx.Bar) error {
	if len(bars) == 0 {
		return nil
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if source == "" {
		source = "tencent"
	}
	var firstErr error
	for _, bar := range bars {
		if bar.Symbol == "" || mkt == "" || bar.TradeDate.IsZero() {
			continue
		}
		tradeDate := bar.TradeDate.Format("2006-01-02")
		barTime := bar.TradeDate.Format("2006-01-02 15:04:05")
		_, err := db.ExecContext(ctx, insertMinuteSQL,
			bar.Symbol, mkt, tradeDate, barTime,
			bar.Open, bar.High, bar.Low, bar.Close, bar.Volume, source)
		if err != nil && firstErr == nil {
			firstErr = err
		}
	}
	return firstErr
}

// writeMinutesDual writes minute bars to Influx first, then mirrors them to MySQL.
// MySQL errors are logged and never fail the Influx write or the job.
// Phase 1 dual-write: readers stay on Influx; Influx is removed only after a later reader cutover.
func writeMinutesDual(ctx context.Context, w minuteInfluxWriter, db dbExecer, market, source string, bars []influx.Bar) (int, error) {
	n, err := w.WriteMinute(ctx, market, bars)
	if err != nil {
		return 0, err
	}
	if mysqlErr := upsertMinuteBars(ctx, db, market, source, bars); mysqlErr != nil {
		slog.Error("phase 1 dual-write: mysql minute upsert failed; influx remains source of truth",
			"market", market, "bars", len(bars), "err", mysqlErr)
	}
	return n, nil
}
