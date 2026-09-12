package store

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/influx"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
)

type stubResult struct{}

func (stubResult) LastInsertId() (int64, error) { return 1, nil }
func (stubResult) RowsAffected() (int64, error) { return 1, nil }

type storedMinute struct {
	Symbol    string
	Market    string
	TradeDate string
	BarTime   string
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
	Source    string
}

type memMinuteDB struct {
	rows  map[string]storedMinute
	fail  error
	calls int
}

func newMemMinuteDB() *memMinuteDB {
	return &memMinuteDB{rows: map[string]storedMinute{}}
}

func minuteKey(symbol, market, barTime string) string {
	return symbol + "\x00" + market + "\x00" + barTime
}

func (m *memMinuteDB) ExecContext(_ context.Context, query string, args ...interface{}) (sql.Result, error) {
	m.calls++
	if m.fail != nil {
		return nil, m.fail
	}
	if !strings.Contains(query, "ON DUPLICATE KEY UPDATE") {
		return nil, errors.New("expected upsert SQL")
	}
	if len(args) < 10 {
		return nil, errors.New("expected 10 bind args")
	}
	row := storedMinute{
		Symbol:    args[0].(string),
		Market:    args[1].(string),
		TradeDate: args[2].(string),
		BarTime:   args[3].(string),
		Open:      args[4].(float64),
		High:      args[5].(float64),
		Low:       args[6].(float64),
		Close:     args[7].(float64),
		Volume:    args[8].(float64),
		Source:    args[9].(string),
	}
	m.rows[minuteKey(row.Symbol, row.Market, row.BarTime)] = row
	return stubResult{}, nil
}

type fakeInfluxWriter struct {
	err    error
	called bool
	market string
	rows   []influx.Bar
}

func (f *fakeInfluxWriter) WriteMinute(_ context.Context, market string, rows []influx.Bar) (int, error) {
	return f.record(market, rows)
}

func (f *fakeInfluxWriter) WriteDaily(_ context.Context, market string, rows []influx.Bar) (int, error) {
	return f.record(market, rows)
}

func (f *fakeInfluxWriter) record(market string, rows []influx.Bar) (int, error) {
	f.called = true
	f.market = market
	f.rows = rows
	if f.err != nil {
		return 0, f.err
	}
	return len(rows), nil
}

func sampleBar(symbol string, ts time.Time, close float64) influx.Bar {
	return influx.Bar{
		Symbol: symbol, TradeDate: ts,
		Open: close - 1, High: close + 1, Low: close - 2, Close: close, Volume: 100,
	}
}

func TestUpsertMinuteBarsReplacesSameSymbolMarketTime(t *testing.T) {
	db := newMemMinuteDB()
	ts := time.Date(2026, 9, 11, 9, 31, 0, 0, time.UTC)
	first := sampleBar("AAPL", ts, 190)
	second := sampleBar("AAPL", ts, 191)
	second.Volume = 250
	ctx := context.Background()
	if _, err := upsertMinuteBars(ctx, db, "us", "tencent", []influx.Bar{first}); err != nil {
		t.Fatal(err)
	}
	if _, err := upsertMinuteBars(ctx, db, "US", "tencent", []influx.Bar{second}); err != nil {
		t.Fatal(err)
	}
	if len(db.rows) != 1 {
		t.Fatalf("want 1 row after upsert, got %d", len(db.rows))
	}
	got := db.rows[minuteKey("AAPL", "US", "2026-09-11 09:31:00")]
	if got.Close != 191 || got.Volume != 250 || got.TradeDate != "2026-09-11" {
		t.Fatalf("upsert did not replace bar: %+v", got)
	}
}

func TestUpsertMinuteBarsKeepsDistinctKeys(t *testing.T) {
	db := newMemMinuteDB()
	ts := time.Date(2026, 9, 11, 9, 31, 0, 0, time.UTC)
	bars := []influx.Bar{
		sampleBar("AAPL", ts, 190),
		sampleBar("AAPL", ts.Add(time.Minute), 191),
		sampleBar("0700.HK", ts, 320),
	}
	if _, err := upsertMinuteBars(context.Background(), db, "US", "tencent", bars[:2]); err != nil {
		t.Fatal(err)
	}
	if _, err := upsertMinuteBars(context.Background(), db, "HK", "tencent", bars[2:]); err != nil {
		t.Fatal(err)
	}
	if len(db.rows) != 3 {
		t.Fatalf("want 3 distinct keys, got %d", len(db.rows))
	}
}

func TestUpsertMinuteSQLTargetsUniqueKey(t *testing.T) {
	sql := strings.ToLower(insertMinuteSQL)
	for _, frag := range []string{
		"insert into market_price_history_minute",
		"on duplicate key update",
		"symbol", "market", "trade_date", "bar_time",
		"open_price", "high_price", "low_price", "close_price", "volume",
	} {
		if !strings.Contains(sql, frag) {
			t.Fatalf("insertMinuteSQL missing %q", frag)
		}
	}
	if strings.Count(insertMinuteSQL, "?") != 10 {
		t.Fatalf("expected 10 placeholders, got %d", strings.Count(insertMinuteSQL, "?"))
	}
}

func TestWriteMinutesDualMySQLFailureFailsJob(t *testing.T) {
	w := &fakeInfluxWriter{}
	db := newMemMinuteDB()
	db.fail = errors.New("mysql unavailable")
	ts := time.Date(2026, 9, 11, 15, 0, 0, 0, time.UTC)
	bars := []influx.Bar{sampleBar("AAPL", ts, 190)}
	n, err := writeMinutesDual(context.Background(), w, db, "US", "tencent", bars)
	if err == nil {
		t.Fatal("mysql error must fail the job")
	}
	if n != 0 {
		t.Fatalf("n=%d", n)
	}
	if !w.called {
		t.Fatal("influx write is still best-effort after mysql failure")
	}
	if db.calls != 1 {
		t.Fatalf("expected mysql attempt, calls=%d", db.calls)
	}
	if len(db.rows) != 0 {
		t.Fatalf("failed mysql write should not store rows")
	}
}

func TestWriteMinutesDualInfluxFailureStillWritesMySQL(t *testing.T) {
	w := &fakeInfluxWriter{err: errors.New("influx 503")}
	db := newMemMinuteDB()
	ts := time.Date(2026, 9, 11, 15, 0, 0, 0, time.UTC)
	bars := []influx.Bar{sampleBar("AAPL", ts, 190)}
	n, err := writeMinutesDual(context.Background(), w, db, "US", "tencent", bars)
	if err != nil {
		t.Fatalf("influx error must not fail the job: %v", err)
	}
	if n != 1 || !w.called {
		t.Fatalf("n=%d called=%v", n, w.called)
	}
	got := db.rows[minuteKey("AAPL", "US", "2026-09-11 15:00:00")]
	if got.Close != 190 {
		t.Fatalf("mysql must store bar when influx is down: %+v", got)
	}
}

func TestWriteMinutesDualNilInfluxStillWritesMySQL(t *testing.T) {
	db := newMemMinuteDB()
	ts := time.Date(2026, 9, 11, 15, 0, 0, 0, time.UTC)
	bars := []influx.Bar{sampleBar("AAPL", ts, 190)}
	n, err := writeMinutesDual(context.Background(), nil, db, "US", "tencent", bars)
	if err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if _, ok := db.rows[minuteKey("AAPL", "US", "2026-09-11 15:00:00")]; !ok {
		t.Fatal("mysql upsert skipped when influx writer is nil")
	}
}

func TestWriteMinutesDualMirrorsSuccessfulInfluxBars(t *testing.T) {
	w := &fakeInfluxWriter{}
	db := newMemMinuteDB()
	ts := time.Date(2026, 9, 11, 9, 31, 0, 0, time.UTC)
	bars := []influx.Bar{sampleBar("600519.SH", ts, 1400)}
	n, err := writeMinutesDual(context.Background(), w, db, "CN", "tencent", bars)
	if err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	got := db.rows[minuteKey("600519.SH", "CN", "2026-09-11 09:31:00")]
	if got.Close != 1400 || got.TradeDate != "2026-09-11" || got.Source != "tencent" {
		t.Fatalf("mysql mirror mismatch: %+v", got)
	}
}

func TestMinuteBarsFromRowsSkipsInvalidTimestamps(t *testing.T) {
	rows := []kline.Row{
		{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-11 09:31:00", Close: 190, Source: "tencent"},
		{Symbol: "AAPL", Market: "US", TradeDate: "not-a-time", Close: 191, Source: "tencent"},
	}
	bars := minuteBarsFromRows(rows)
	if len(bars) != 1 || bars[0].Close != 190 {
		t.Fatalf("bars=%v", bars)
	}
	if minuteSource(rows) != "tencent" {
		t.Fatalf("source=%s", minuteSource(rows))
	}
}

func TestMinuteSchemaSQLReadyForMigrate(t *testing.T) {
	path := filepath.Join("..", "..", "..", "..", "sql", "market-price-history-minute.sql")
	body, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("sql file missing (sql_migrate scans sql/*.sql): %v", err)
	}
	text := string(body)
	for _, frag := range []string{
		"CREATE TABLE IF NOT EXISTS market_price_history_minute",
		"UNIQUE KEY uniq_symbol_market_bar_time (symbol, market, bar_time)",
		"KEY ix_market_bar_time (market, bar_time)",
		"KEY ix_trade_date (trade_date)",
		"trade_date VARCHAR(10)",
		"phase 1",
	} {
		if !strings.Contains(text, frag) {
			t.Fatalf("schema SQL missing %q", frag)
		}
	}
}
