package influx

import (
	"context"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
)

func TestQueryKlinesFromMySQLStore(t *testing.T) {
	mem := klineread.NewMemStore()
	mem.UpsertDaily(klineread.DailyRow{Symbol: "SPY", Market: "US", TradeDate: "2026-09-10", Close: 500})
	mem.UpsertDaily(klineread.DailyRow{Symbol: "DIA", Market: "US", TradeDate: "2026-09-10", Close: 350})
	r := NewReaderWithStore(mem)
	grouped, err := r.QueryKlinesMany(context.Background(), "US", []string{"SPY", "DIA"}, "-280d", 260)
	if err != nil {
		t.Fatalf("many: %v", err)
	}
	if grouped["SPY"][0].Close != 500 || grouped["DIA"][0].Close != 350 {
		t.Fatalf("grouped=%v", grouped)
	}
}

func TestEmptyHSIMinutesNoInventedBars(t *testing.T) {
	r := NewReaderWithStore(klineread.NewMemStore())
	bars, err := r.QueryMinuteKlines(context.Background(), "HK", "HSI.HK", "-2d", "now()", 100)
	if err != nil || len(bars) != 0 {
		t.Fatalf("HSI.HK must be empty, got %v err=%v", bars, err)
	}
}

func TestNoInfluxClientOnReadPath(t *testing.T) {
	r := NewReaderWithStore(klineread.NewMemStore())
	bars, err := r.QueryKlines(context.Background(), "US", "QQQ", "-30d", 2)
	if err != nil || len(bars) != 0 {
		t.Fatalf("empty QQQ: %v err=%v", bars, err)
	}
}
