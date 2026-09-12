package klineread

import (
	"context"
	"strings"
	"testing"
	"time"
)

func TestUpsertReadDailyRange(t *testing.T) {
	mem := NewMemStore()
	mem.UpsertDaily(DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-01", Open: 100, High: 110, Low: 90, Close: 105, Volume: 1000})
	mem.UpsertDaily(DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-02", Open: 105, High: 115, Low: 100, Close: 112, Volume: 1100})
	mem.UpsertDaily(DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-02", Open: 106, High: 116, Low: 101, Close: 113, Volume: 1200})

	r := New(mem)
	bars, err := r.QueryDaily(context.Background(), "US", "AAPL", "2026-09-01", "2026-09-02", nil)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if len(bars) != 2 {
		t.Fatalf("got %d bars, want 2", len(bars))
	}
	if bars[0].Date != "2026-09-01" || deref(bars[0].Close) != 105 {
		t.Fatalf("first=%+v", bars[0])
	}
	if bars[1].Date != "2026-09-02" || deref(bars[1].Close) != 113 {
		t.Fatalf("upsert did not replace 2026-09-02: %+v", bars[1])
	}
}

func TestUpsertReadMinuteRange(t *testing.T) {
	mem := NewMemStore()
	t1 := time.Date(2026, 9, 11, 9, 31, 0, 0, beijing)
	t2 := time.Date(2026, 9, 11, 9, 32, 0, 0, beijing)
	mem.UpsertMinute(MinuteRow{Symbol: "AAPL", Market: "US", BarTime: t1, Open: 1, High: 2, Low: 0.5, Close: 1.5, Volume: 10})
	mem.UpsertMinute(MinuteRow{Symbol: "AAPL", Market: "US", BarTime: t2, Open: 1.5, High: 2.5, Low: 1, Close: 2, Volume: 12})
	mem.UpsertMinute(MinuteRow{Symbol: "AAPL", Market: "US", BarTime: t2, Open: 1.6, High: 2.6, Low: 1.1, Close: 2.1, Volume: 13})

	r := New(mem)
	bars, err := r.QueryMinute(context.Background(), "US", "AAPL", "2026-09-11 09:31:00", "2026-09-11 09:32:00", nil)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if len(bars) != 2 {
		t.Fatalf("got %d bars, want 2", len(bars))
	}
	if bars[0].Date != "2026-09-11 09:31" {
		t.Fatalf("minute date=%q", bars[0].Date)
	}
	if deref(bars[1].Close) != 2.1 {
		t.Fatalf("upsert did not replace 09:32 close=%v", deref(bars[1].Close))
	}
}

func TestEmptyHSIMinute(t *testing.T) {
	mem := NewMemStore()
	mem.UpsertMinute(MinuteRow{
		Symbol: "0700.HK", Market: "HK",
		BarTime: time.Date(2026, 9, 11, 9, 31, 0, 0, beijing),
		Close:   400,
	})
	r := New(mem)
	for _, sym := range []string{"HSI", "HSI.HK"} {
		bars, err := r.QueryMinute(context.Background(), "HK", sym, "-2d", "now()", nil)
		if err != nil {
			t.Fatalf("%s: %v", sym, err)
		}
		if len(bars) != 0 {
			t.Fatalf("%s should be empty (never stored), got %d", sym, len(bars))
		}
	}
}

func TestNoSilentRemapShangzhengToPingan(t *testing.T) {
	mem := NewMemStore()
	mem.UpsertDaily(DailyRow{Symbol: "000001.SZ", Market: "CN", TradeDate: "2026-09-11", Close: 12.3})
	r := New(mem)
	bars, err := r.QueryDaily(context.Background(), "CN", "000001", "-30d", "now()", nil)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if len(bars) != 0 {
		t.Fatalf("000001 must not remap to 000001.SZ, got %d bars close=%v", len(bars), deref(bars[0].Close))
	}
	sz, err := r.QueryDaily(context.Background(), "CN", "000001.SZ", "-30d", "now()", nil)
	if err != nil || len(sz) != 1 || deref(sz[0].Close) != 12.3 {
		t.Fatalf("exact 000001.SZ: bars=%v err=%v", sz, err)
	}
}

func TestRelativeRangeAndLimit(t *testing.T) {
	mem := NewMemStore()
	mem.UpsertDaily(DailyRow{Symbol: "SPY", Market: "US", TradeDate: "2020-01-02", Close: 1})
	mem.UpsertDaily(DailyRow{Symbol: "SPY", Market: "US", TradeDate: nowBeijing().AddDate(0, 0, -3).Format("2006-01-02"), Close: 2})
	mem.UpsertDaily(DailyRow{Symbol: "SPY", Market: "US", TradeDate: nowBeijing().AddDate(0, 0, -1).Format("2006-01-02"), Close: 3})
	r := New(mem)
	lim := 1
	bars, err := r.QueryDaily(context.Background(), "US", "SPY", "-10d", "now()", &lim)
	if err != nil {
		t.Fatalf("query: %v", err)
	}
	if len(bars) != 1 || deref(bars[0].Close) != 3 {
		t.Fatalf("last-N in range: %+v", bars)
	}
}

func TestQueryDailyManyAndLatest(t *testing.T) {
	mem := NewMemStore()
	mem.UpsertDaily(DailyRow{Symbol: "QQQ", Market: "US", TradeDate: "2026-09-10", Close: 400})
	mem.UpsertDaily(DailyRow{Symbol: "DIA", Market: "US", TradeDate: "2026-09-10", Close: 350})
	r := New(mem)
	grouped, err := r.QueryLatestDailyValues(context.Background(), "US", []string{"QQQ", "DIA", "MISSING"}, 2, "-30d")
	if err != nil {
		t.Fatalf("many: %v", err)
	}
	if grouped["QQQ"][0].Close != 400 || grouped["DIA"][0].Close != 350 {
		t.Fatalf("grouped=%v", grouped)
	}
	if _, ok := grouped["MISSING"]; ok {
		t.Fatalf("missing symbol should be omitted: %v", grouped)
	}
}

func TestInvalidSymbolAndRangeEmpty(t *testing.T) {
	mem := NewMemStore()
	mem.UpsertDaily(DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-11", Close: 1})
	r := New(mem)
	bars, err := r.QueryDaily(context.Background(), "US", "AAPL;drop", "-2y", "now()", nil)
	if err != nil || len(bars) != 0 {
		t.Fatalf("invalid symbol: bars=%v err=%v", bars, err)
	}
	bars, err = r.QueryDaily(context.Background(), "US", "AAPL", "not-a-time", "now()", nil)
	if err != nil || len(bars) != 0 {
		t.Fatalf("invalid range: bars=%v err=%v", bars, err)
	}
}

func TestParseBoundRelative(t *testing.T) {
	now := time.Date(2026, 9, 12, 12, 0, 0, 0, beijing)
	got, ok := parseBound("-2d", now)
	if !ok || formatDailyDate(got) != "2026-09-10" {
		t.Fatalf("got %v ok=%v", got, ok)
	}
	got, ok = parseBound("now()", now)
	if !ok || !got.Equal(now) {
		t.Fatalf("now() %v", got)
	}
}

func TestDailyPageSQL(t *testing.T) {
	q, args := dailyPageSQL("US", "2026-01-01", 100, 20)
	for _, part := range []string{"market_price_history_daily", "market=?", "trade_date>=?", "LIMIT ? OFFSET ?"} {
		if !strings.Contains(q, part) {
			t.Fatalf("missing %q in %s", part, q)
		}
	}
	if len(args) != 4 || args[0] != "US" || args[1] != "2026-01-01" || args[2] != 100 || args[3] != 20 {
		t.Fatalf("args=%v", args)
	}
	q, args = dailyPageSQL("HK", "", 10, 0)
	if strings.Contains(q, "trade_date>=?") {
		t.Fatalf("empty since should omit date filter: %s", q)
	}
	if len(args) != 3 {
		t.Fatalf("args=%v", args)
	}
}
