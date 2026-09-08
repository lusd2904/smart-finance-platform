package heat

import (
	"strings"
	"testing"
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
			return `{"data":{"diff":[{"f12":"600519","f14":"茅台","f2":1500,"f3":1.1,"f6":8000000000,"f20":15000000000}]}}`, nil
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
		}
	}
	if !found {
		t.Fatalf("candidates=%+v", cands)
	}
}
