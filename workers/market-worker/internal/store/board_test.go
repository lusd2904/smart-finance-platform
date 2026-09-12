package store

import (
	"context"
	"os"
	"strings"
	"testing"
)

type memBoardKlines struct {
	byMarket map[string]map[string][]dailyBar
	called   bool
	markets  []string
}

func (m *memBoardKlines) LatestDaily(_ context.Context, market string, symbols []string, n int, _ string) (map[string][]dailyBar, error) {
	m.called = true
	m.markets = append(m.markets, market)
	out := map[string][]dailyBar{}
	src := m.byMarket[strings.ToUpper(market)]
	if src == nil {
		return out, nil
	}
	if n <= 0 {
		n = 2
	}
	for _, sym := range symbols {
		bars := src[sym]
		if len(bars) == 0 {
			continue
		}
		if len(bars) > n {
			bars = bars[len(bars)-n:]
		}
		out[sym] = bars
	}
	return out, nil
}

func TestAssembleBoardQuotesUsesMySQLSource(t *testing.T) {
	instruments := []instrumentRow{
		{Symbol: "AAPL", Name: "苹果", Market: "US", Category: "stock"},
		{Symbol: "^GSPC", Name: "标普500", Market: "US", Category: "index"},
		{Symbol: "EMPTY", Name: "无K线", Market: "US", Category: "stock"},
	}
	bars := map[string][]dailyBar{
		"AAPL": {
			{Date: "2026-09-10", Open: 189, High: 191, Low: 188, Close: 190, Volume: 10},
			{Date: "2026-09-11", Open: 190, High: 193, Low: 189, Close: 192, Volume: 12},
		},
		"^GSPC": {
			{Date: "2026-09-11", Open: 5000, High: 5010, Low: 4990, Close: 5005, Volume: 1},
		},
	}
	quotes := assembleBoardQuotes(instruments, bars)
	if len(quotes) != 3 {
		t.Fatalf("quotes=%d", len(quotes))
	}
	if quotes[0]["source"] != "mysql" || quotes[0]["price"] != 192.0 {
		t.Fatalf("AAPL quote=%v", quotes[0])
	}
	if quotes[0]["changeRate"] != 1.0526 {
		t.Fatalf("AAPL changeRate=%v", quotes[0]["changeRate"])
	}
	if quotes[1]["source"] != "mysql" || quotes[1]["category"] != "index" {
		t.Fatalf("index quote=%v", quotes[1])
	}
	if quotes[2]["source"] != "none" || quotes[2]["bars"] != 0 {
		t.Fatalf("empty quote must not invent bars: %v", quotes[2])
	}
}

func TestRefreshBoardQuotesCacheReadsInjectedMySQLStore(t *testing.T) {
	src := &memBoardKlines{byMarket: map[string]map[string][]dailyBar{
		"US": {
			"AAPL": {
				{Date: "2026-09-10", Close: 190},
				{Date: "2026-09-11", Close: 192},
			},
		},
	}}
	s := &Service{
		boardKlines: src,
		db:          nil,
		reader:      nil,
		rdb:         nil,
	}
	// listAllInstruments needs db; cover assemble via latestDailyBars wiring.
	grouped, err := s.latestDailyBars(context.Background(), "US", []string{"AAPL", "MSFT"}, 2, "-60d")
	if err != nil {
		t.Fatal(err)
	}
	if !src.called {
		t.Fatal("board_warmup must use the MySQL kline source")
	}
	if len(grouped["AAPL"]) != 2 || grouped["AAPL"][1].Close != 192 {
		t.Fatalf("AAPL bars=%v", grouped["AAPL"])
	}
	if _, ok := grouped["MSFT"]; ok {
		t.Fatal("must not invent missing symbols")
	}
}

func TestLatestDailySQLTargetsMySQLNotFlux(t *testing.T) {
	sql := strings.ToLower(latestDailySQL)
	for _, frag := range []string{
		"from market_price_history_daily",
		"symbol=?",
		"market=?",
		"trade_date",
		"open_price", "high_price", "low_price", "close_price", "volume",
		"limit ?",
	} {
		if !strings.Contains(sql, frag) {
			t.Fatalf("latestDailySQL missing %q", frag)
		}
	}
	if strings.Contains(sql, "daily_kline") || strings.Contains(sql, "from(") {
		t.Fatal("board warmup SQL must not be Flux")
	}
}

func TestBoardWarmupSourceHasNoFluxRead(t *testing.T) {
	for _, name := range []string{"board.go", "board_klines.go"} {
		body, err := os.ReadFile(name)
		if err != nil {
			t.Fatal(err)
		}
		text := string(body)
		for _, banned := range []string{
			"QueryLatestKlines",
			"/api/v2/query",
			"parseFluxCSV",
			"from(bucket",
		} {
			if strings.Contains(text, banned) {
				t.Fatalf("%s still Flux-reads via %q", name, banned)
			}
		}
	}
}

func TestDailyWindowParsesRelativeDays(t *testing.T) {
	from, to := dailyWindow("-60d")
	if len(from) != 10 || len(to) != 10 {
		t.Fatalf("from=%q to=%q", from, to)
	}
	if to < from {
		t.Fatalf("window inverted from=%s to=%s", from, to)
	}
}
