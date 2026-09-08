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
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		gotToken = r.Header.Get("X-Internal-Token")
		raw, _ := io.ReadAll(r.Body)
		var body map[string]interface{}
		if err := json.Unmarshal(raw, &body); err != nil {
			t.Fatalf("body: %v", err)
		}
		gotType, _ = body["type"].(string)
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"ok": true})
	}))
	defer srv.Close()

	out, err := New(srv.URL, "tok").Run(context.Background(), "strategy_evaluate", map[string]interface{}{"profile": "balanced"})
	if err != nil {
		t.Fatal(err)
	}
	if gotType != "strategy_evaluate" || gotToken != "tok" {
		t.Fatalf("type=%s token=%s", gotType, gotToken)
	}
	if ok, _ := out["ok"].(bool); !ok {
		t.Fatalf("%+v", out)
	}
}

func TestClientRequiresURL(t *testing.T) {
	if _, err := New("", "").Run(context.Background(), "strategy_evaluate", nil); err == nil {
		t.Fatal("expected missing INTERNAL_JOBS_URL")
	}
}
