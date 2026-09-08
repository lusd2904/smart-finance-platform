package tradeexec

import (
	"os"
	"strings"
	"testing"
)

func TestSubmitGatedHaltAndPaperDefaults(t *testing.T) {
	ok, reason := SubmitGated(true, true, true, true, "人工")
	if ok || !strings.Contains(reason, "停机") {
		t.Fatal(ok, reason)
	}
	ok, reason = SubmitGated(true, true, false, false, "")
	if ok || !strings.Contains(reason, "未开启自动交易") {
		t.Fatal(ok, reason)
	}
	ok, _ = SubmitGated(true, true, true, false, "")
	if !ok {
		t.Fatal("expected submit allowed")
	}
}

func TestDeprecatedPaperFlagsAreNotRequired(t *testing.T) {
	_ = os.Unsetenv("LONGPORT_PAPERTRADING")
	_ = os.Unsetenv("REQUIRE_PAPER")
	if flags := DeprecatedPaperFlagsPresent(); len(flags) != 0 {
		t.Fatalf("unexpected flags %v", flags)
	}
}

func TestValidateOrderInput(t *testing.T) {
	if ValidateOrderInput("", "buy", 1, "LO", 10, true) == "" {
		t.Fatal("blank symbol")
	}
	if ValidateOrderInput("AAPL", "hold", 1, "LO", 10, true) == "" {
		t.Fatal("bad side")
	}
	if ValidateOrderInput("AAPL", "buy", 0, "LO", 10, true) == "" {
		t.Fatal("qty")
	}
	if ValidateOrderInput("AAPL", "buy", 1, "FOO", 10, true) == "" {
		t.Fatal("type")
	}
	if ValidateOrderInput("AAPL", "buy", 1, "LO", 0, false) == "" {
		t.Fatal("limit needs price")
	}
	if ValidateOrderInput("AAPL", "buy", 1, "MO", 0, false) != "" {
		t.Fatal("MO may omit price")
	}
	if ValidateOrderInput("AAPL", "卖出", 2, "LO", 11, true) != "" {
		t.Fatal("chinese sell should pass")
	}
}

func TestSizeDailyListOrder(t *testing.T) {
	acct := Account{Balances: []Balance{{Currency: "USD", NetAssets: 100000, AvailableCash: 100000}}}
	// 15% of 100000 = 15000, capped at 8000; price 80 → 100 shares
	qty := SizeDailyListOrder(acct, "US", 80, 0)
	if qty != 100 {
		t.Fatalf("qty=%d", qty)
	}
	qty = SizeDailyListOrder(acct, "HK", 10, 0)
	if qty%100 != 0 || qty < 100 {
		t.Fatalf("hk lot %d", qty)
	}
	empty := SizeDailyListOrder(Account{}, "US", 10, 0)
	if empty != 1 {
		t.Fatalf("fallback lot %d", empty)
	}
}

func TestBuyQuantityFromUSDUsesHKD(t *testing.T) {
	fx := FxRates{USDHKD: 7.8}
	// $1000 → 7800 HKD / 78 = 100 shares
	qty := BuyQuantityFromUSD(1000, 78, "HK", fx)
	if qty != 100 {
		t.Fatalf("qty=%d", qty)
	}
}
