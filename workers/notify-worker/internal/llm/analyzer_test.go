package llm

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGatewayFailoverCodes(t *testing.T) {
	for _, code := range []int{401, 402, 403, 408, 502, 503, 524, 529} {
		if !ShouldFailover(code) {
			t.Fatalf("expected failover for %d", code)
		}
	}
	for _, code := range []int{200, 400, 404, 429, 500} {
		if ShouldFailover(code) {
			t.Fatalf("%d should not failover", code)
		}
	}
}

func TestAnalyzeSetsMaxTokens(t *testing.T) {
	var got map[string]interface{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if err := json.Unmarshal(body, &got); err != nil {
			t.Errorf("decode payload: %v", err)
		}
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"error":"invalid api key"}`))
	}))
	defer srv.Close()

	c := &Client{http: srv.Client()}
	resp := c.Analyze(context.Background(), srv.URL, "dead-key", "grok-4.6", []NewsItem{
		{Source: "x", Title: "t", Content: "c", PubTime: "2026-09-08 12:00:00"},
	}, 0.2)
	if resp.OK {
		t.Fatal("expected 401 failure")
	}
	if resp.Code != http.StatusUnauthorized {
		t.Fatalf("code=%d", resp.Code)
	}
	assertMaxTokens(t, got)
}

func TestAnalyzeReturnsFailoverCode402(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusPaymentRequired)
		_, _ = w.Write([]byte(`{"error":"max_tokens too large"}`))
	}))
	defer srv.Close()
	c := &Client{http: srv.Client()}
	resp := c.Analyze(context.Background(), srv.URL, "k", "x-ai/grok-4.6", []NewsItem{{Title: "t"}}, 0.2)
	if resp.OK || resp.Code != http.StatusPaymentRequired {
		t.Fatalf("ok=%v code=%d", resp.OK, resp.Code)
	}
	if !ShouldFailover(resp.Code) {
		t.Fatal("402 must trigger next-model failover")
	}
}

func TestChatCompletionSetsMaxTokens(t *testing.T) {
	var got map[string]interface{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		if err := json.Unmarshal(body, &got); err != nil {
			t.Errorf("decode payload: %v", err)
		}
		w.WriteHeader(http.StatusPaymentRequired)
		_, _ = w.Write([]byte(`{"error":"credits"}`))
	}))
	defer srv.Close()

	c := &Client{http: srv.Client()}
	_, err := c.ChatCompletion(context.Background(), srv.URL, "k", "x-ai/grok-4.6", "sys", nil, "hi", 0.2)
	if err == nil {
		t.Fatal("expected 402 error")
	}
	assertMaxTokens(t, got)
}

func assertMaxTokens(t *testing.T, payload map[string]interface{}) {
	t.Helper()
	if payload == nil {
		t.Fatal("missing request payload")
	}
	raw, ok := payload["max_tokens"]
	if !ok {
		t.Fatal("max_tokens missing from chat/completions payload")
	}
	n, ok := raw.(float64)
	if !ok || int(n) != DefaultMaxTokens {
		t.Fatalf("max_tokens=%v want %d", raw, DefaultMaxTokens)
	}
}
