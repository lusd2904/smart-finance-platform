package longbridge

import (
	"strings"
	"testing"
)

func TestSignRequestStable(t *testing.T) {
	got := SignRequest("GET", "/v1/quote/filings", "symbol=AAPL.US", "", "app-key", "access-token", "1770000000000", "app-secret")
	if !strings.HasPrefix(got, "HMAC-SHA256 SignedHeaders=authorization;x-api-key;x-timestamp, Signature=") {
		t.Fatalf("header=%s", got)
	}
	sig := strings.TrimPrefix(got, "HMAC-SHA256 SignedHeaders=authorization;x-api-key;x-timestamp, Signature=")
	if len(sig) != 64 {
		t.Fatalf("signature length=%d value=%s", len(sig), sig)
	}
	again := SignRequest("GET", "/v1/quote/filings", "symbol=AAPL.US", "", "app-key", "access-token", "1770000000000", "app-secret")
	if again != got {
		t.Fatal("signature not stable")
	}
	other := SignRequest("GET", "/v1/quote/filings", "symbol=TSLA.US", "", "app-key", "access-token", "1770000000000", "app-secret")
	if other == got {
		t.Fatal("different query must change signature")
	}
}

func TestSignRequestIncludesBodyHash(t *testing.T) {
	empty := SignRequest("POST", "/v1/x", "", "", "k", "t", "1", "s")
	withBody := SignRequest("POST", "/v1/x", "", `{"a":1}`, "k", "t", "1", "s")
	if empty == withBody {
		t.Fatal("body must participate in signature")
	}
}
