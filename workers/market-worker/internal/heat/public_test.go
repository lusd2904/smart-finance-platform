package heat

import (
	"strings"
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/kline"
)

func TestParseTencentQuote(t *testing.T) {
	text := `v_sh000001="1~上证指数~000001~3200.12~3180.00~10~100~200~300~400~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~15:00:00~0~0.63~0~0~0~123~4500000000~0";`
	q, err := ParseTencentQuote(text)
	if err != nil {
		t.Fatal(err)
	}
	last, _ := q["last"].(*float64)
	if last == nil || *last != 3200.12 {
		t.Fatalf("last=%v", q["last"])
	}
	chg, _ := q["change_pct"].(*float64)
	if chg == nil || *chg != 0.63 {
		t.Fatalf("change=%v", q["change_pct"])
	}
	turn, _ := q["turnover"].(*float64)
	if turn == nil || *turn != 4500000000 {
		t.Fatalf("turnover=%v", q["turnover"])
	}
}

func TestParseTencentQuoteEmpty(t *testing.T) {
	q, err := ParseTencentQuote("v_sh000001=\"\";")
	if err != nil || len(q) != 0 {
		t.Fatalf("%v %#v", err, q)
	}
}

func TestExtractJSONP(t *testing.T) {
	raw, err := extractJSONP(`var xx=({"data":[{"symbol":"AAPL"}]});`)
	if err != nil {
		t.Fatal(err)
	}
	if string(raw) != `{"data":[{"symbol":"AAPL"}]}` {
		t.Fatalf("raw=%s", raw)
	}
}

func TestSinaUSRowAmountFallback(t *testing.T) {
	row := sinaUSRow(map[string]any{"symbol": "aapl", "cname": "苹果", "price": "10", "volume": "5", "chg": "1.2", "mktcap": "100"})
	if row.Symbol != "AAPL" {
		t.Fatalf("symbol=%s", row.Symbol)
	}
	if row.Turnover == nil || *row.Turnover != 50 {
		t.Fatalf("turnover=%v", row.Turnover)
	}
}

func TestCandidateFromEastmoneyAndDerived(t *testing.T) {
	c := candidateFromEastmoney(map[string]any{
		"f12": "000001", "f14": "平安", "f2": 10.0, "f3": 1.0, "f6": 1e9, "f20": 2e11,
		"f15": 10.5, "f16": 9.5, "f18": 10.0,
	})
	if c.ChangeAmount == nil || *c.ChangeAmount < 0.09 || *c.ChangeAmount > 0.11 {
		t.Fatalf("derived changeAmount=%v", c.ChangeAmount)
	}
	if c.Amplitude == nil || *c.Amplitude != 10 {
		t.Fatalf("derived amplitude=%v", c.Amplitude)
	}
}

func TestSinaUSRowParsesExtras(t *testing.T) {
	row := sinaUSRow(map[string]any{
		"symbol": "MSFT", "cname": "微软", "price": "100", "volume": "2",
		"chg": "2", "diff": "2", "pe": "28.5", "high": "102", "low": "98", "preclose": "98",
	})
	if row.ChangeAmount == nil || *row.ChangeAmount != 2 {
		t.Fatalf("changeAmount=%v", row.ChangeAmount)
	}
	if row.PE == nil || *row.PE != 28.5 {
		t.Fatalf("pe=%v", row.PE)
	}
	if row.Amplitude == nil || *row.Amplitude < 4.08 || *row.Amplitude > 4.09 {
		t.Fatalf("amplitude=%v", row.Amplitude)
	}
}

func TestFetchPublicUniverseUsesInjectedHTTP(t *testing.T) {
	orig := getText
	defer func() { getText = orig }()
	getText = func(rawURL string) (string, error) {
		switch {
		case strings.Contains(rawURL, "qt.gtimg.cn"):
			return `v_sh000001="1~idx~000001~3200~3180~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~15:00:00~0~1.10~0~0~0~0~1000000000~0";`, nil
		case strings.Contains(rawURL, "ulist.np"):
			return `{"data":{"diff":[{"f3":1.2,"f6":2000000000,"f14":"上证","f104":2000,"f105":800,"f106":100}]}}`, nil
		case strings.Contains(rawURL, "clist/get"):
			return `{"data":{"diff":[{"f12":"600519","f14":"茅台","f2":1500,"f3":1.1,"f4":16.5,"f6":8000000000,"f7":2.4,"f8":0.85,"f9":22.1,"f10":1.6,"f20":15000000000,"f62":120000000}]}}`, nil
		case strings.Contains(rawURL, "getHQNodeData"):
			return `[{"code":"000001","name":"平安","mktcap":25000000000,"amount":9000000000,"changepercent":-0.5,"trade":10}]`, nil
		default:
			return `[]`, nil
		}
	}
	cands, extras := FetchPublicUniverse("CN")
	if extras.IndexChange == nil || *extras.IndexChange != 1.2 {
		t.Fatalf("index=%v", extras.IndexChange)
	}
	if extras.Advance == nil || *extras.Advance != 2000 {
		t.Fatalf("advance=%v", extras.Advance)
	}
	found := false
	for _, c := range cands {
		if c.Symbol == "600519" {
			found = true
			if c.MarketCap == nil || *c.MarketCap != 15000000000 {
				t.Fatalf("cap=%v", c.MarketCap)
			}
			if c.ChangeAmount == nil || *c.ChangeAmount != 16.5 {
				t.Fatalf("changeAmount=%v", c.ChangeAmount)
			}
			if c.TurnoverRate == nil || *c.TurnoverRate != 0.85 {
				t.Fatalf("turnoverRate=%v", c.TurnoverRate)
			}
			if c.VolumeRatio == nil || *c.VolumeRatio != 1.6 {
				t.Fatalf("volumeRatio=%v", c.VolumeRatio)
			}
			if c.Amplitude == nil || *c.Amplitude != 2.4 {
				t.Fatalf("amplitude=%v", c.Amplitude)
			}
			if c.PE == nil || *c.PE != 22.1 {
				t.Fatalf("pe=%v", c.PE)
			}
			if c.MainNetInflow == nil || *c.MainNetInflow != 120000000 {
				t.Fatalf("mainNetInflow=%v", c.MainNetInflow)
			}
		}
	}
	if !found {
		t.Fatalf("candidates=%+v", cands)
	}
}

func TestUSHeatIndexMapsGSPCToUsINX(t *testing.T) {
	if got := usHeatIndexTencent(); got != "usINX" {
		t.Fatalf("usHeatIndexTencent=%q want usINX (^GSPC, not usGSPC)", got)
	}
	tencent, sina, ok := kline.VendorIndex("^GSPC", "US")
	if !ok || tencent != "usINX" || sina != ".INX" {
		t.Fatalf("VendorIndex(^GSPC,US)=(%q,%q,%v)", tencent, sina, ok)
	}
	tencent, sina, ok = kline.VendorIndex("^DJI", "US")
	if !ok || tencent != "usDJI" || sina != ".DJI" {
		t.Fatalf("VendorIndex(^DJI,US)=(%q,%q,%v)", tencent, sina, ok)
	}
	tencent, sina, ok = kline.VendorIndex("^IXIC", "US")
	if !ok || tencent != "usIXIC" || sina != ".IXIC" {
		t.Fatalf("VendorIndex(^IXIC,US)=(%q,%q,%v)", tencent, sina, ok)
	}
}

func TestDailyBarChangePct(t *testing.T) {
	got := DailyBarChangePct(5050, 5000)
	if got == nil || *got != 1 {
		t.Fatalf("change=%v", got)
	}
	if DailyBarChangePct(0, 5000) != nil || DailyBarChangePct(5000, 0) != nil {
		t.Fatal("zero closes must be nil")
	}
}

func TestFetchUSIndexChangeUsesTencentINX(t *testing.T) {
	orig := getText
	defer func() { getText = orig }()
	sawINX := false
	getText = func(rawURL string) (string, error) {
		switch {
		case strings.Contains(rawURL, "qt.gtimg.cn"):
			if !strings.Contains(rawURL, "usINX") {
				t.Fatalf("US heat must query usINX, got %s", rawURL)
			}
			sawINX = true
			return `v_usINX="1~标普500~INX~5050~5000~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~15:00:00~0~1.00~0~0~0~0~1000000000~0";`, nil
		case strings.Contains(rawURL, "ulist.np"):
			return `{"data":{"diff":[]}}`, nil
		case strings.Contains(rawURL, "clist/get"):
			return `{"data":{"diff":[{"f12":"AAPL","f14":"苹果","f2":100,"f3":1.1,"f6":8000000000,"f20":2500000000000}]}}`, nil
		default:
			return `[]`, nil
		}
	}
	_, extras := FetchPublicUniverse("US")
	if !sawINX {
		t.Fatal("expected Tencent usINX quote")
	}
	if extras.IndexChange == nil || *extras.IndexChange != 1 {
		t.Fatalf("index=%v want 1.00 from usINX daily change", extras.IndexChange)
	}
}
