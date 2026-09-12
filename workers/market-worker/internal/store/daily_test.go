package store

import (
	"context"
	"database/sql"
	"errors"
	"os"
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
)

type storedDaily struct {
	Symbol    string
	Market    string
	TradeDate string
	Open      float64
	High      float64
	Low       float64
	Close     float64
	Volume    float64
	Source    string
}

type memDailyDB struct {
	rows  map[string]storedDaily
	fail  error
	calls int
}

func newMemDailyDB() *memDailyDB {
	return &memDailyDB{rows: map[string]storedDaily{}}
}

func dailyKey(symbol, tradeDate string) string {
	return symbol + "\x00" + tradeDate
}

func (m *memDailyDB) ExecContext(_ context.Context, query string, args ...interface{}) (sql.Result, error) {
	m.calls++
	if m.fail != nil {
		return nil, m.fail
	}
	if !strings.Contains(query, "ON DUPLICATE KEY UPDATE") {
		return nil, errors.New("expected upsert SQL")
	}
	if len(args) < 9 {
		return nil, errors.New("expected 9 bind args")
	}
	row := storedDaily{
		Symbol:    args[0].(string),
		Market:    args[1].(string),
		TradeDate: args[2].(string),
		Open:      args[3].(float64),
		High:      args[4].(float64),
		Low:       args[5].(float64),
		Close:     args[6].(float64),
		Volume:    args[7].(float64),
		Source:    args[8].(string),
	}
	m.rows[dailyKey(row.Symbol, row.TradeDate)] = row
	return stubResult{}, nil
}

func sampleDailyRow(symbol, market, tradeDate string, close float64) kline.Row {
	return kline.Row{
		Symbol: symbol, Market: market, TradeDate: tradeDate,
		Open: close - 1, High: close + 1, Low: close - 2, Close: close, Volume: 1e9,
		Source: "sina",
	}
}

func TestUpsertDailyBarsReplacesSameSymbolDate(t *testing.T) {
	db := newMemDailyDB()
	first := sampleDailyRow("^GSPC", "US", "2026-09-11", 6500)
	second := sampleDailyRow("^GSPC", "US", "2026-09-11", 6510)
	second.Volume = 2e9
	ctx := context.Background()
	if _, err := upsertDailyBars(ctx, db, []kline.Row{first}); err != nil {
		t.Fatal(err)
	}
	if _, err := upsertDailyBars(ctx, db, []kline.Row{second}); err != nil {
		t.Fatal(err)
	}
	if len(db.rows) != 1 {
		t.Fatalf("want 1 row after upsert, got %d", len(db.rows))
	}
	got := db.rows[dailyKey("^GSPC", "2026-09-11")]
	if got.Close != 6510 || got.Volume != 2e9 || got.Market != "US" {
		t.Fatalf("upsert did not replace bar: %+v", got)
	}
}

func TestUpsertDailySQLTargetsUniqueKey(t *testing.T) {
	sql := strings.ToLower(insertDailySQL)
	for _, frag := range []string{
		"insert into market_price_history_daily",
		"on duplicate key update",
		"symbol", "market", "trade_date",
		"open_price", "high_price", "low_price", "close_price", "volume",
	} {
		if !strings.Contains(sql, frag) {
			t.Fatalf("insertDailySQL missing %q", frag)
		}
	}
	if strings.Count(insertDailySQL, "?") != 9 {
		t.Fatalf("expected 9 placeholders, got %d", strings.Count(insertDailySQL, "?"))
	}
}

func TestWriteDailyDualMySQLFailureFailsJob(t *testing.T) {
	w := &fakeInfluxWriter{}
	db := newMemDailyDB()
	db.fail = errors.New("mysql unavailable")
	rows := []kline.Row{sampleDailyRow("AAPL", "US", "2026-09-11", 190)}
	n, err := writeDailyDual(context.Background(), w, db, "US", rows)
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

func TestWriteDailyDualInfluxFailureStillWritesMySQL(t *testing.T) {
	w := &fakeInfluxWriter{err: errors.New("influx 503")}
	db := newMemDailyDB()
	rows := []kline.Row{sampleDailyRow("^GSPC", "US", "2026-09-11", 6500)}
	n, err := writeDailyDual(context.Background(), w, db, "US", rows)
	if err != nil {
		t.Fatalf("influx error must not fail the job: %v", err)
	}
	if n != 1 || !w.called {
		t.Fatalf("n=%d called=%v", n, w.called)
	}
	got := db.rows[dailyKey("^GSPC", "2026-09-11")]
	if got.Close != 6500 || got.Market != "US" {
		t.Fatalf("mysql must store Friday bar when influx is down: %+v", got)
	}
}

func TestWriteDailyDualNilInfluxStillWritesMySQL(t *testing.T) {
	db := newMemDailyDB()
	rows := []kline.Row{
		sampleDailyRow("^GSPC", "US", "2026-09-11", 6500),
		sampleDailyRow("AAPL", "US", "2026-09-11", 190),
	}
	n, err := writeDailyDual(context.Background(), nil, db, "US", rows)
	if err != nil || n != 2 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	if _, ok := db.rows[dailyKey("^GSPC", "2026-09-11")]; !ok {
		t.Fatal("index daily skipped when influx writer is nil")
	}
	if _, ok := db.rows[dailyKey("AAPL", "2026-09-11")]; !ok {
		t.Fatal("featured daily skipped when influx writer is nil")
	}
}

func TestWriteDailyDualMirrorsSuccessfulInfluxBars(t *testing.T) {
	w := &fakeInfluxWriter{}
	db := newMemDailyDB()
	rows := []kline.Row{sampleDailyRow("600519.SH", "CN", "2026-09-11", 1400)}
	n, err := writeDailyDual(context.Background(), w, db, "CN", rows)
	if err != nil || n != 1 {
		t.Fatalf("n=%d err=%v", n, err)
	}
	got := db.rows[dailyKey("600519.SH", "2026-09-11")]
	if got.Close != 1400 || got.Source != "sina" {
		t.Fatalf("mysql mirror mismatch: %+v", got)
	}
	if !w.called || w.market != "CN" || len(w.rows) != 1 || w.rows[0].Close != 1400 {
		t.Fatalf("influx companion mismatch: called=%v market=%s rows=%v", w.called, w.market, w.rows)
	}
}

func TestToInfluxBarsSkipsInvalidDates(t *testing.T) {
	rows := []kline.Row{
		sampleDailyRow("^GSPC", "US", "2026-09-11", 6500),
		sampleDailyRow("^GSPC", "US", "not-a-date", 6510),
	}
	bars := toInfluxBars(rows)
	if len(bars) != 1 || bars[0].Close != 6500 {
		t.Fatalf("bars=%v", bars)
	}
}

func TestSyncSymbolWiresWriteDailyDual(t *testing.T) {
	body, err := os.ReadFile("service.go")
	if err != nil {
		t.Fatal(err)
	}
	fn := funcSource(string(body), "func (s *Service) SyncSymbol")
	if fn == "" {
		t.Fatal("SyncSymbol missing")
	}
	if !strings.Contains(fn, "writeDailyDual") {
		t.Fatal("SyncSymbol must persist daily bars via writeDailyDual (MySQL required, Influx best-effort)")
	}
	if strings.Contains(fn, "s.influx.WriteDaily") {
		t.Fatal("SyncSymbol must not fail closed on Influx WriteDaily")
	}
}

func funcSource(src, signature string) string {
	idx := strings.Index(src, signature)
	if idx < 0 {
		return ""
	}
	rest := src[idx:]
	if next := strings.Index(rest[1:], "\nfunc "); next >= 0 {
		return rest[:next+1]
	}
	return rest
}

func TestSyncSymbolWritePathIgnoresInfluxError(t *testing.T) {
	// SyncSymbol must persist MySQL via writeDailyDual even when Influx fails.
	// This is the live-hub failure: eod_kline_sync walked symbols, WriteDaily
	// 503'd, and Friday ^GSPC never reached saveMySQL.
	w := &fakeInfluxWriter{err: errors.New("connection refused")}
	db := newMemDailyDB()
	rows := []kline.Row{sampleDailyRow("^GSPC", "US", "2026-09-11", 6500)}
	svcN, svcErr := writeDailyDual(context.Background(), w, db, "US", rows)
	if svcErr != nil {
		t.Fatalf("SyncSymbol/EOD must not lose MySQL bars because Influx is down: %v", svcErr)
	}
	if svcN != 1 {
		t.Fatalf("want mysql count 1, got %d", svcN)
	}
	if !w.called {
		t.Fatal("influx companion should still be attempted")
	}
	if _, ok := db.rows[dailyKey("^GSPC", "2026-09-11")]; !ok {
		t.Fatal("^GSPC Friday bar missing from MySQL after Influx failure")
	}
}
