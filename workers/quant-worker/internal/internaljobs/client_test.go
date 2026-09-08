package internaljobs

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestClientPostsToGoInternalJobs(t *testing.T) {
	var gotType, gotToken string
	var gotPayload map[string]interface{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/internal/jobs/run" {
			t.Fatalf("path %s", r.URL.Path)
		}
		gotToken = r.Header.Get("X-Internal-Token")
		raw, _ := io.ReadAll(r.Body)
		var body map[string]interface{}
		if err := json.Unmarshal(raw, &body); err != nil {
			t.Fatalf("body: %v", err)
		}
		gotType, _ = body["type"].(string)
		gotPayload, _ = body["payload"].(map[string]interface{})
		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"ok": true, "signals": []map[string]interface{}{},
		})
	}))
	defer srv.Close()

	c := New(srv.URL+"/internal/jobs/run", "secret")
	out, err := c.Run(context.Background(), "strategy_evaluate", map[string]interface{}{
		"profile": "balanced", "userId": 1,
	})
	if err != nil {
		t.Fatal(err)
	}
	if gotType != "strategy_evaluate" || gotToken != "secret" {
		t.Fatalf("type=%s token=%s", gotType, gotToken)
	}
	if gotPayload["profile"] != "balanced" {
		t.Fatalf("payload %+v", gotPayload)
	}
	if ok, _ := out["ok"].(bool); !ok {
		t.Fatalf("response %+v", out)
	}
}

func TestClientRequiresURL(t *testing.T) {
	c := New("", "")
	_, err := c.Run(context.Background(), "strategy_evaluate", nil)
	if err == nil {
		t.Fatal("expected missing INTERNAL_JOBS_URL")
	}
}
