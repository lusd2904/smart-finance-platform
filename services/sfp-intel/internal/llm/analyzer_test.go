package llm_test

import (
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/llm"
)

func TestGatewayFailoverCodes(t *testing.T) {
	for _, code := range []int{502, 503, 524} {
		if !llm.GatewayFailoverCodes[code] {
			t.Fatalf("expected failover for %d", code)
		}
	}
	if llm.GatewayFailoverCodes[200] {
		t.Fatal("200 should not failover")
	}
}
