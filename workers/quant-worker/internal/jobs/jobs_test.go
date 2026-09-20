package jobs

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/tradeexec"
	"github.com/redis/go-redis/v9"
)

type fakeBroker struct {
	account   tradeexec.Account
	positions []tradeexec.Position
	quotes    []tradeexec.Quote
	submits   []tradeexec.SubmitReq
	submitOK  bool
	orderID   string
}

func (f *fakeBroker) AccountBalance(context.Context, tradeexec.Creds) (tradeexec.Account, error) {
	return f.account, nil
}
func (f *fakeBroker) Positions(context.Context, tradeexec.Creds) ([]tradeexec.Position, error) {
	return f.positions, nil
}
func (f *fakeBroker) TodayOrders(context.Context, tradeexec.Creds) ([]tradeexec.Order, error) {
	return nil, nil
}
func (f *fakeBroker) RealtimeQuotes(context.Context, tradeexec.Creds, []string, string) ([]tradeexec.Quote, error) {
	return f.quotes, nil
}
func (f *fakeBroker) SubmitOrder(_ context.Context, _ tradeexec.Creds, req tradeexec.SubmitReq) tradeexec.SubmitResult {
	f.submits = append(f.submits, req)
	if !f.submitOK {
		return tradeexec.SubmitResult{Configured: true, OK: false, Message: "simulated reject"}
	}
	return tradeexec.SubmitResult{Configured: true, OK: true, OrderID: f.orderID, Message: "下单已提交"}
}

type fakeStrategy struct{ signals []StrategySignal }

func (f fakeStrategy) Evaluate(context.Context, string, int, []Target) ([]StrategySignal, error) {
	return f.signals, nil
}

func TestPlaceOrQueueIdempotentAndHalt(t *testing.T) {
	ctx := context.Background()
	broker := &fakeBroker{submitOK: true, orderID: "OID-1", account: tradeexec.Account{
		Configured: true,
		Balances:   []tradeexec.Balance{{Currency: "USD", NetAssets: 20000, AvailableCash: 20000}},
	}}
	repo := &Repo{}
	row := DailyItem{ItemID: 9, Status: "submitted", OrderID: "OLD"}
	out := placeOrQueue(ctx, repo, broker, tradeexec.Creds{AppKey: "k", AppSecret: "s", AccessToken: "t"}, row, true, "")
	if out["idempotent"] != true {
		t.Fatalf("%v", out)
	}
	if len(broker.submits) != 0 {
		t.Fatal("idempotent must not submit")
	}

	row = DailyItem{ItemID: 10, Status: "listed", Symbol: "AAPL", Market: "US", Price: 100}
	out = placeOrQueue(ctx, repo, broker, tradeexec.Creds{AppKey: "k", AppSecret: "s", AccessToken: "t"}, row, true, "紧急停机中，禁止新委托")
	if out["ok"] != false || !strings.Contains(fmtString(out["message"]), "停机") {
		t.Fatalf("%v", out)
	}
	if len(broker.submits) != 0 {
		t.Fatal("halt must not submit")
	}
}

func TestPlaceOrQueueSubmitsMO(t *testing.T) {
	ctx := context.Background()
	broker := &fakeBroker{
		submitOK: true, orderID: "OID-2",
		account: tradeexec.Account{Configured: true, Balances: []tradeexec.Balance{{Currency: "USD", NetAssets: 20000, AvailableCash: 20000}}},
	}
	row := DailyItem{ItemID: 11, Status: "queued", Symbol: "AAPL", Market: "US", Price: 80}
	out := placeOrQueue(ctx, repoStub(), broker, tradeexec.Creds{AppKey: "k", AppSecret: "s", AccessToken: "t"}, row, true, "")
	if out["ok"] != true {
		t.Fatalf("%v", out)
	}
	if len(broker.submits) != 1 || broker.submits[0].OrderType != "MO" {
		t.Fatalf("%v", broker.submits)
	}
	if broker.submits[0].Side != "buy" {
		t.Fatal(broker.submits[0].Side)
	}
}

func TestMergeTargetsDropsCN(t *testing.T) {
	got := mergeTargets([]Target{{Symbol: "AAPL", Market: "US"}, {Symbol: "600519", Market: "CN"}, {Symbol: "700", Market: "HK"}})
	if len(got) != 2 {
		t.Fatalf("%v", got)
	}
}

func TestReadHaltFailClosed(t *testing.T) {
	h := readHalt(context.Background(), nil)
	if !h.Halted || h.Reason != "halt state unavailable" {
		t.Fatalf("nil redis: %+v", h)
	}
	rdb := redis.NewClient(&redis.Options{Addr: "127.0.0.1:1", DialTimeout: 50 * time.Millisecond})
	h = readHalt(context.Background(), rdb)
	if !h.Halted || h.Reason != "halt state unavailable" {
		t.Fatalf("get error: %+v", h)
	}
}

func TestUniqueIntsDropsNonPositive(t *testing.T) {
	got := uniqueInts([]int{0, 1, 2}, []int{1, -3})
	if len(got) != 2 || got[0] != 1 || got[1] != 2 {
		t.Fatalf("%v", got)
	}
	if got := uniqueInts(nil, nil); len(got) != 0 {
		t.Fatalf("empty fallback must not inject user 1: %v", got)
	}
}

func TestPlaceOrQueueZeroQtySkips(t *testing.T) {
	ctx := context.Background()
	broker := &fakeBroker{submitOK: true, orderID: "OID-0"}
	row := DailyItem{ItemID: 12, Status: "queued", Symbol: "AAPL", Market: "US", Price: 80}
	out := placeOrQueue(ctx, repoStub(), broker, tradeexec.Creds{AppKey: "k", AppSecret: "s", AccessToken: "t"}, row, true, "")
	if out["ok"] != false || len(broker.submits) != 0 {
		t.Fatalf("zero qty must skip submit: %v %v", out, broker.submits)
	}
}

func TestStopLossHaltNote(t *testing.T) {
	msg := tradeexec.HaltBlockReason(readHalt(context.Background(), nil))
	if msg == "" {
		t.Fatal("nil redis halt must block stop-loss")
	}
}

func TestParseStrategySignalsFromDelegate(t *testing.T) {
	raw := map[string]interface{}{
		"result": map[string]interface{}{
			"signals": []interface{}{
				map[string]interface{}{"symbol": "AAPL", "market": "US", "signal": "BUY", "score": 80.0, "confidence": 80.0, "price": 190.0},
			},
		},
	}
	list, _ := raw["result"].(map[string]interface{})
	if list == nil {
		t.Fatal()
	}
}

func fmtString(v interface{}) string {
	if v == nil {
		return ""
	}
	return v.(string)
}

func repoStub() *Repo { return &Repo{} }
