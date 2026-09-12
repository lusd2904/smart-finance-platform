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
// Readers use this table; Influx write is still the dual-write companion.
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

func upsertMinuteBars(ctx context.Context, db dbExecer, market, source string, bars []influx.Bar) (int, error) {
	if len(bars) == 0 {
		return 0, nil
	}
	mkt := strings.ToUpper(strings.TrimSpace(market))
	if source == "" {
		source = "tencent"
	}
	n := 0
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

// writeMinutesDual upserts minute bars to MySQL (source of truth for reads), then
// best-effort WriteMinute to Influx when w is non-nil. Influx errors are logged
// and do not fail the job. MySQL upsert errors fail the job.
func writeMinutesDual(ctx context.Context, w minuteInfluxWriter, db dbExecer, market, source string, bars []influx.Bar) (int, error) {
	n, mysqlErr := upsertMinuteBars(ctx, db, market, source, bars)
	if w != nil {
		if _, influxErr := w.WriteMinute(ctx, market, bars); influxErr != nil {
			slog.Error("minute dual-write: influx write failed; mysql is source of truth",
				"market", market, "bars", len(bars), "err", influxErr)
		}
	}
	if mysqlErr != nil {
		return n, mysqlErr
	}
	return n, nil
}
