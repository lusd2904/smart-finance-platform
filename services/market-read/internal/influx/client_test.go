package influx

import (
	"context"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/kline"
)

type recordingSource struct {
	dailyCalls  int
	minuteCalls int
	daily       []klineread.Bar
	minute      []klineread.Bar
}

func (r *recordingSource) QueryDaily(context.Context, string, string, string, string, *int) ([]klineread.Bar, error) {
	r.dailyCalls++
	return r.daily, nil
}

func (r *recordingSource) QueryMinute(context.Context, string, string, string, string, *int) ([]klineread.Bar, error) {
	r.minuteCalls++
	return r.minute, nil
}

type boomInflux struct {
	t     *testing.T
	calls int
}

func (b *boomInflux) QueryDaily(context.Context, string, string, string, string, *int) ([]klineread.Bar, error) {
	b.calls++
	b.t.Fatal("influx daily must not be called on the read path")
	return nil, nil
}

func (b *boomInflux) QueryMinute(context.Context, string, string, string, string, *int) ([]klineread.Bar, error) {
	b.calls++
	b.t.Fatal("influx minute must not be called on the read path")
	return nil, nil
}

// mysqlFirst is the production shape: MySQL source only. Influx is present on the
// struct so a test can prove GetKlineSeries never touches it.
type mysqlFirst struct {
	mysql  barSource
	influx barSource
}

func (m mysqlFirst) QueryDaily(ctx context.Context, market, symbol, start, stop string, limit *int) ([]klineread.Bar, error) {
	return m.mysql.QueryDaily(ctx, market, symbol, start, stop, limit)
}

func (m mysqlFirst) QueryMinute(ctx context.Context, market, symbol, start, stop string, limit *int) ([]klineread.Bar, error) {
	return m.mysql.QueryMinute(ctx, market, symbol, start, stop, limit)
}

func f64(v float64) *float64 { return &v }

func TestGetKlineSeriesRoutesDailyVsMinute(t *testing.T) {
	src := &recordingSource{
		daily: []klineread.Bar{{Date: "2026-09-01", Close: f64(10)}},
		minute: []klineread.Bar{
			{Date: "2026-09-11 09:31", Open: f64(1), High: f64(2), Low: f64(1), Close: f64(1.5), Volume: f64(10)},
			{Date: "2026-09-11 09:32", Open: f64(1.5), High: f64(2), Low: f64(1), Close: f64(1.6), Volume: f64(11)},
		},
	}
	c := NewWithSource(src)

	daily, err := c.GetKlineSeries(context.Background(), "US", "AAPL", "daily", "-2y", "now()", nil)
	if err != nil || src.dailyCalls != 1 || src.minuteCalls != 0 {
		t.Fatalf("daily route: err=%v daily=%d minute=%d", err, src.dailyCalls, src.minuteCalls)
	}
	if len(daily) != 1 || daily[0].Date != "2026-09-01" {
		t.Fatalf("daily bars=%v", daily)
	}

	src.dailyCalls, src.minuteCalls = 0, 0
	intra, err := c.GetKlineSeries(context.Background(), "US", "AAPL", "intraday", "", "now()", nil)
	if err != nil || src.minuteCalls != 1 || src.dailyCalls != 0 {
		t.Fatalf("intraday route: err=%v daily=%d minute=%d", err, src.dailyCalls, src.minuteCalls)
	}
	if len(intra) != 2 {
		t.Fatalf("intraday bars=%d", len(intra))
	}

	src.dailyCalls, src.minuteCalls = 0, 0
	if _, err := c.GetKlineSeries(context.Background(), "US", "AAPL", "weekly", "-3y", "now()", nil); err != nil || src.dailyCalls != 1 || src.minuteCalls != 0 {
		t.Fatalf("weekly should resample daily: err=%v daily=%d minute=%d", err, src.dailyCalls, src.minuteCalls)
	}
	if how := kline.DailyResampleRule("weekly"); how != "W" {
		t.Fatalf("weekly rule=%s", how)
	}
}

func TestGetKlineSeriesDoesNotCallInflux(t *testing.T) {
	mem := klineread.NewMemStore()
	mem.UpsertDaily(klineread.DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-11", Close: 190})
	influx := &boomInflux{t: t}
	c := NewWithSource(mysqlFirst{mysql: klineread.New(mem), influx: influx})
	bars, err := c.GetKlineSeries(context.Background(), "US", "AAPL", "daily", "-30d", "now()", nil)
	if err != nil || len(bars) != 1 {
		t.Fatalf("mysql path: bars=%v err=%v", bars, err)
	}
	if influx.calls != 0 {
		t.Fatalf("influx was called %d times", influx.calls)
	}

	empty, err := c.GetKlineSeries(context.Background(), "HK", "HSI", "1min", "-2d", "now()", nil)
	if err != nil {
		t.Fatalf("empty HSI err=%v", err)
	}
	if len(empty) != 0 {
		t.Fatalf("HSI minutes must stay empty, got %d", len(empty))
	}
	if influx.calls != 0 {
		t.Fatalf("empty HSI must not fall back to Influx")
	}
}

func TestEmptyMySQLIsNotInfluxFallback(t *testing.T) {
	influx := &boomInflux{t: t}
	c := NewWithSource(mysqlFirst{mysql: klineread.New(klineread.NewMemStore()), influx: influx})
	bars, err := c.GetKlineSeries(context.Background(), "HK", "HSI.HK", "intraday", "", "now()", nil)
	if err != nil || len(bars) != 0 {
		t.Fatalf("empty series must return empty without Influx, got %v err=%v", bars, err)
	}
	if influx.calls != 0 {
		t.Fatal("influx fallback is forbidden")
	}
}
