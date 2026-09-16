package store

import (
	"context"
	"os"
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/klineread"
	mwinflux "github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/influx"
)

func TestFeaturedBoardReadsMySQLStoreNotInflux(t *testing.T) {
	mem := klineread.NewMemStore()
	mem.UpsertDaily(klineread.DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-14", Close: 220, Volume: 10})
	mem.UpsertDaily(klineread.DailyRow{Symbol: "AAPL", Market: "US", TradeDate: "2026-09-15", Close: 222, Volume: 12})
	mem.UpsertDaily(klineread.DailyRow{Symbol: "0700.HK", Market: "HK", TradeDate: "2026-09-15", Close: 400, Volume: 8})

	svc := &Service{reader: mwinflux.NewReaderWithStore(mem)}
	board, err := svc.featuredBoard(context.Background())
	if err != nil {
		t.Fatalf("featuredBoard: %v", err)
	}
	if len(board) == 0 {
		t.Fatal("expected featured pool rows")
	}

	bySymbol := map[string]map[string]interface{}{}
	for _, row := range board {
		sym, _ := row["symbol"].(string)
		bySymbol[sym] = row
	}
	aapl := bySymbol["AAPL"]
	if aapl == nil {
		t.Fatal("AAPL missing from board")
	}
	if aapl["close"] != 222.0 {
		t.Fatalf("AAPL close=%v", aapl["close"])
	}
	if aapl["change"] != 2.0 {
		t.Fatalf("AAPL change=%v", aapl["change"])
	}
	if aapl["asOf"] != "2026-09-15" {
		t.Fatalf("AAPL asOf=%v", aapl["asOf"])
	}
	hk := bySymbol["0700.HK"]
	if hk == nil || hk["close"] != 400.0 {
		t.Fatalf("0700.HK=%v", hk)
	}
	if hk["change"] != nil {
		t.Fatalf("single-bar HK row must not invent a prior close: %v", hk["change"])
	}
}

func TestFeaturedBoardEmptyStoreSucceeds(t *testing.T) {
	svc := &Service{reader: mwinflux.NewReaderWithStore(klineread.NewMemStore())}
	board, err := svc.featuredBoard(context.Background())
	if err != nil {
		t.Fatalf("empty store must not fail job 107: %v", err)
	}
	if len(board) == 0 {
		t.Fatal("featured pool must still emit rows with nil quotes")
	}
	for _, row := range board {
		if row["close"] != nil {
			t.Fatalf("empty store invented a close: %v", row)
		}
	}
}

func TestIndicatorRefreshSourcesHaveNoInfluxClient(t *testing.T) {
	files := []string{
		"service.go",
		"../influx/reader.go",
		"../../Dockerfile",
	}
	banned := []string{
		"sentiment-influxdb",
		"/api/v2/query",
		"/api/v2/write",
		"application/vnd.flux",
		"net/http",
		"from(bucket:",
	}
	for _, name := range files {
		body, err := os.ReadFile(name)
		if err != nil {
			t.Fatalf("read %s: %v", name, err)
		}
		text := string(body)
		if name == "../../Dockerfile" {
			if !strings.Contains(text, "COPY services/klineread") {
				t.Fatal("quant-worker Dockerfile must COPY services/klineread")
			}
			continue
		}
		for _, frag := range banned {
			if strings.Contains(text, frag) {
				t.Fatalf("%s still mentions Influx/Flux %q", name, frag)
			}
		}
	}
}
