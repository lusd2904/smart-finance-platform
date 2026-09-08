package heat

import "testing"

func TestNormalizeMarket(t *testing.T) {
	m, err := NormalizeMarket("cn")
	if err != nil || m != "CN" {
		t.Fatalf("expected CN, got %s err=%v", m, err)
	}
	_, err = NormalizeMarket("XX")
	if err == nil {
		t.Fatalf("expected error for unsupported market")
	}
}
