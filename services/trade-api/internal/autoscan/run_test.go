package autoscan

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/internaljobs"
	"github.com/lusd2904/smart-finance-platform/services/trade-api/internal/platform"
	"github.com/redis/go-redis/v9"
)

func TestStrategyEvaluatorUsesInternalJobs(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"signals": []map[string]interface{}{
				{"symbol": "AAPL", "market": "US", "signal": "buy", "score": 81.0, "confidence": 72.0, "reason": "ok", "price": 190.0},
			},
		})
	}))
	defer srv.Close()

	eval := &StrategyEvaluator{Jobs: internaljobs.New(srv.URL, "tok")}
	got, err := eval.Evaluate(context.Background(), "balanced", 1, []platform.Target{{Symbol: "AAPL", Market: "US"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Symbol != "AAPL" || got[0].Signal != "BUY" {
		t.Fatalf("%+v", got)
	}
}

func TestStrategyEvaluatorRequiresClient(t *testing.T) {
	if _, err := (&StrategyEvaluator{}).Evaluate(context.Background(), "balanced", 1, nil); err == nil {
		t.Fatal("expected unconfigured client")
	}
}

func TestRunWatchlistCycleRequiresUserID(t *testing.T) {
	_, err := RunWatchlistCycle(context.Background(), nil, nil, nil, nil, Keys{}, RunInput{})
	if err == nil || !strings.Contains(err.Error(), "缺少 userId") {
		t.Fatalf("err=%v", err)
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
