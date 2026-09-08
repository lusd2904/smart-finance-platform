package quotes

import (
	"context"
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/tencent"
)

type stubFetcher map[string]tencent.Quote

func (s stubFetcher) FetchBatch(_ context.Context, codes []string) (map[string]tencent.Quote, error) {
	out := map[string]tencent.Quote{}
	for _, code := range codes {
		if q, ok := s[code]; ok {
			out[code] = q
		}
	}
	return out, nil
}

func f64(v float64) *float64 { return &v }

func TestIndexQuotesFromFetcher(t *testing.T) {
	svc := &Service{Fetcher: stubFetcher{
		"usINX":    {Name: "标普500", Last: f64(5000), PrevClose: f64(4900), ChangePct: f64(2.04), QuoteTime: "10:00"},
		"sh000001": {Name: "上证", Last: f64(3000), PrevClose: f64(3010), ChangePct: f64(-0.33)},
	}}
	out := svc.IndexQuotes(context.Background())
	if out["cached"] != false {
		t.Fatalf("cached=%v", out["cached"])
	}
	items, _ := out["items"].([]map[string]interface{})
	if len(items) != 2 {
		t.Fatalf("items=%d %#v", len(items), out["items"])
	}
	if items[0]["symbol"] != "usINX" || items[0]["market"] != "US" {
		t.Fatalf("first=%#v", items[0])
	}
}

func TestLiveQuotesTencentShape(t *testing.T) {
	svc := &Service{Fetcher: stubFetcher{
		"usAAPL":  {Name: "苹果", Last: f64(227.52), PrevClose: f64(226.01), ChangePct: f64(0.67), QuoteTime: "10:00"},
		"hk00700": {Name: "腾讯", Last: f64(400), PrevClose: f64(390), ChangePct: f64(2.56)},
	}}
	out := svc.LiveQuotes(context.Background(), []Pair{{"AAPL", "US"}, {"00700", "HK"}})
	if out["source"] != "tencent" {
		t.Fatalf("source=%v", out["source"])
	}
	items, _ := out["items"].([]map[string]interface{})
	if len(items) != 2 {
		t.Fatalf("items=%d", len(items))
	}
	if items[0]["symbol"] != "AAPL" || items[0]["source"] != "tencent" {
		t.Fatalf("%#v", items[0])
	}
	if items[1]["symbol"] != "00700" || items[1]["market"] != "HK" {
		t.Fatalf("%#v", items[1])
	}
}

func TestLiveQuotesEmpty(t *testing.T) {
	svc := &Service{Fetcher: stubFetcher{}}
	out := svc.LiveQuotes(context.Background(), nil)
	if out["source"] != "empty" {
		t.Fatalf("%#v", out)
	}
}
