package jobs

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/lusd2904/smart-finance-platform/workers/quant-worker/internal/internaljobs"
)

func TestInternalJobsStrategyEvaluate(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"result": map[string]interface{}{
				"signals": []map[string]interface{}{
					{"symbol": "AAPL", "market": "US", "signal": "buy", "score": 80.0, "confidence": 70.0, "reason": "ok", "price": 100.0},
				},
			},
		})
	}))
	defer srv.Close()

	s := &InternalJobsStrategy{Client: internaljobs.New(srv.URL, "tok")}
	got, err := s.Evaluate(context.Background(), "balanced", 7, []Target{{Symbol: "AAPL", Market: "US"}})
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 1 || got[0].Symbol != "AAPL" || got[0].Signal != "BUY" || got[0].Confidence != 70 {
		t.Fatalf("%+v", got)
	}
}

func TestInternalJobsStrategyRequiresClient(t *testing.T) {
	s := &InternalJobsStrategy{}
	_, err := s.Evaluate(context.Background(), "balanced", 1, nil)
	if err == nil {
		t.Fatal("expected unconfigured client")
	}
}
