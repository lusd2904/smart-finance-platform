package longbridge

import (
	"strings"
	"testing"
)

func TestSignRequestStable(t *testing.T) {
	got := SignRequest("GET", "/v1/asset/stock", "", "", "app-key", "access-token", "1770000000000", "app-secret")
	if !strings.HasPrefix(got, "HMAC-SHA256 SignedHeaders=authorization;x-api-key;x-timestamp, Signature=") {
		t.Fatalf("header=%s", got)
	}
	sig := strings.TrimPrefix(got, "HMAC-SHA256 SignedHeaders=authorization;x-api-key;x-timestamp, Signature=")
	if len(sig) != 64 {
		t.Fatalf("signature length=%d value=%s", len(sig), sig)
	}
	again := SignRequest("GET", "/v1/asset/stock", "", "", "app-key", "access-token", "1770000000000", "app-secret")
	if again != got {
		t.Fatal("signature not stable")
	}
}

func TestParseSymbolMarket(t *testing.T) {
	sym, mkt := ParseSymbolMarket("0700.HK", "")
	if sym != "0700" || mkt != "HK" {
		t.Fatalf("%s %s", sym, mkt)
	}
	sym, mkt = ParseSymbolMarket("600519.SH", "US")
	if sym != "600519" || mkt != "CN" {
		t.Fatalf("%s %s", sym, mkt)
	}
	sym, mkt = ParseSymbolMarket("AAPL", "")
	if sym != "AAPL" || mkt != "US" {
		t.Fatalf("%s %s", sym, mkt)
	}
}
