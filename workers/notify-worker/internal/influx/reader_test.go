package influx

import (
	"context"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
)

func TestQueryKlinesFromMySQLStore(t *testing.T) {
	mem := klineread.NewMemStore()
	mem.UpsertDaily(klineread.DailyRow{Symbol: "SPY", Market: "US", TradeDate: "2026-09-10", Close: 500})
	mem.UpsertDaily(klineread.DailyRow{Symbol: "QQQ", Market: "US", TradeDate: "2026-09-10", Close: 400})
	r := NewReaderWithStore(mem)
	grouped, err := r.QueryKlinesMany(context.Background(), "US", []string{"SPY", "QQQ"}, "-30d", 10)
	if err != nil {
		t.Fatalf("many: %v", err)
	}
	if grouped["SPY"][0].Close != 500 || grouped["QQQ"][0].Close != 400 {
		t.Fatalf("grouped=%v", grouped)
	}
	latest, err := r.QueryLatestKlines(context.Background(), "US", []string{"SPY"}, 1, "-30d")
	if err != nil || latest["SPY"][0].Close != 500 {
		t.Fatalf("latest=%v err=%v", latest, err)
	}
}

func TestEmptyHSIMinutesNoInventedBars(t *testing.T) {
	mem := klineread.NewMemStore()
	mem.UpsertMinute(klineread.MinuteRow{
		Symbol: "0700.HK", Market: "HK",
		BarTime: time.Date(2026, 9, 11, 9, 31, 0, 0, time.FixedZone("CST", 8*3600)),
		Close:   400,
	})
	r := NewReaderWithStore(mem)
	bars, err := r.QueryMinuteKlines(context.Background(), "HK", "HSI", "-2d", "now()", 100)
	if err != nil || len(bars) != 0 {
		t.Fatalf("HSI must be empty, got %v err=%v", bars, err)
	}
}

func TestNoInfluxClientOnReadPath(t *testing.T) {
	// Reader has no HTTP/Flux field; constructing with a mem store must succeed
	// without any Influx config or client.
	r := NewReaderWithStore(klineread.NewMemStore())
	bars, err := r.QueryKlines(context.Background(), "US", "DIA", "-30d", 2)
	if err != nil || len(bars) != 0 {
		t.Fatalf("empty DIA: %v err=%v", bars, err)
	}
	if r.src == nil {
		t.Fatal("mysql store missing")
	}
}
