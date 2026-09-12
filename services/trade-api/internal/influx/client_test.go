package influx

import (
	"context"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
)

type recordingSource struct {
	dailyCalls  int
	minuteCalls int
	daily       []klineread.Bar
	minute      []klineread.Bar
	latest      string
}

func (r *recordingSource) QueryDaily(context.Context, string, string, string, string, *int) ([]klineread.Bar, error) {
	r.dailyCalls++
	return r.daily, nil
}

func (r *recordingSource) QueryMinute(context.Context, string, string, string, string, *int) ([]klineread.Bar, error) {
	r.minuteCalls++
	return r.minute, nil
}

func (r *recordingSource) LatestDailyDate(context.Context, string, string) (string, error) {
	return r.latest, nil
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
func (b *boomInflux) LatestDailyDate(context.Context, string, string) (string, error) {
	b.calls++
	b.t.Fatal("influx LatestDate must not be called on the read path")
	return "", nil
}

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
func (m mysqlFirst) LatestDailyDate(ctx context.Context, market, symbol string) (string, error) {
	return m.mysql.LatestDailyDate(ctx, market, symbol)
}

func f64(v float64) *float64 { return &v }

func TestGetKlineSeriesRoutesDailyVsMinute(t *testing.T) {
	src := &recordingSource{
		daily:  []klineread.Bar{{Date: "2026-09-01", Close: f64(10)}},
		minute: []klineread.Bar{{Date: "2026-09-11 09:31", Close: f64(1.5)}},
	}
	c := NewWithSource(src)
	if _, err := c.GetKlineSeries(context.Background(), "US", "AAPL", "daily", "-2y", "now()", nil); err != nil || src.dailyCalls != 1 || src.minuteCalls != 0 {
		t.Fatalf("daily route daily=%d minute=%d err=%v", src.dailyCalls, src.minuteCalls, err)
	}
	src.dailyCalls, src.minuteCalls = 0, 0
	if _, err := c.GetKlineSeries(context.Background(), "US", "AAPL", "1min", "", "now()", nil); err != nil || src.minuteCalls != 1 || src.dailyCalls != 0 {
		t.Fatalf("minute route daily=%d minute=%d err=%v", src.dailyCalls, src.minuteCalls, err)
	}
}

func TestGetKlineSeriesDoesNotCallInflux(t *testing.T) {
	influx := &boomInflux{t: t}
	c := NewWithSource(mysqlFirst{mysql: klineread.New(klineread.NewMemStore()), influx: influx})
	bars, err := c.GetKlineSeries(context.Background(), "HK", "HSI", "intraday", "", "now()", nil)
	if err != nil || len(bars) != 0 {
		t.Fatalf("empty HSI via mysql: %v err=%v", bars, err)
	}
	if influx.calls != 0 {
		t.Fatal("influx fallback is forbidden")
	}
}

func TestLatestDateUsesMySQLSource(t *testing.T) {
	src := &recordingSource{latest: "2026-09-11"}
	c := NewWithSource(src)
	got, err := c.LatestDate(context.Background(), "US", "AAPL")
	if err != nil || got != "2026-09-11" {
		t.Fatalf("latest=%q err=%v", got, err)
	}
}
