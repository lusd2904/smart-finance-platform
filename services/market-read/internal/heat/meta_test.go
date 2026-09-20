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

func TestCNIndexSymbolIsShanghaiComposite(t *testing.T) {
	if MarketMeta["CN"].IndexSymbol != "000001.SH" {
		t.Fatalf("CN IndexSymbol=%q want 000001.SH", MarketMeta["CN"].IndexSymbol)
	}
}
