package tradeexec

import (
	"strings"
	"testing"
)

func TestNormalizeSide(t *testing.T) {
	for _, s := range []string{"BUY", "b", "买", "买入"} {
		if NormalizeSide(s) != "buy" {
			t.Fatalf("%s -> %s", s, NormalizeSide(s))
		}
	}
	if NormalizeSide("卖出") != "sell" {
		t.Fatal(NormalizeSide("卖出"))
	}
}

func TestTodayBuyNotionalFromOrders(t *testing.T) {
	count, notional := TodayBuyNotionalFromOrders([]Order{
		{Side: "Buy", Status: "Submitted", Quantity: 10, Price: 5},
		{Side: "Sell", Status: "Filled", Quantity: 2, Price: 8},
		{Side: "Buy", Status: "cancelled", Quantity: 100, Price: 9},
	})
	if count != 2 {
		t.Fatalf("count=%d", count)
	}
	if notional != 50 {
		t.Fatalf("notional=%v", notional)
	}
}

func TestBuyBlockedReason(t *testing.T) {
	if msg := BuyBlockedReason(0, 10000, 10000, 0, 0, 0, 0.2, 0.1); !strings.Contains(msg, "无法估算") {
		t.Fatal(msg)
	}
	if msg := BuyBlockedReason(100, 0, 1000, 0, 0, 0, 0.2, 0.1); !strings.Contains(msg, "净资产为 0") {
		t.Fatal(msg)
	}
	// 20% of 10000 = 2000 daily; already used 1900; order 200 blocked
	msg := BuyBlockedReason(200, 10000, 5000, 0, 0, 1900, 0.2, 0.1)
	if !strings.Contains(msg, "日内买入上限") {
		t.Fatal(msg)
	}
	// symbol cap 10% of 10000 = 1000; existing 950; order 100 blocked
	msg = BuyBlockedReason(100, 10000, 5000, 0, 950, 0, 0.2, 0.1)
	if !strings.Contains(msg, "单标的仓位上限") {
		t.Fatal(msg)
	}
	msg = BuyBlockedReason(100, 10000, 5000, 9950, 0, 0, 0.2, 0.1)
	if !strings.Contains(msg, "总持仓") {
		t.Fatal(msg)
	}
	msg = BuyBlockedReason(200, 10000, 50, 0, 0, 0, 0.2, 0.1)
	if !strings.Contains(msg, "可用现金不足") {
		t.Fatal(msg)
	}
	if msg := BuyBlockedReason(100, 10000, 5000, 0, 0, 0, 0.2, 0.1); msg != "" {
		t.Fatal(msg)
	}
}

func TestSellBlockedReason(t *testing.T) {
	if !strings.Contains(SellBlockedReason(0, 10), "必须大于 0") {
		t.Fatal()
	}
	if !strings.Contains(SellBlockedReason(1, 0), "无可用持仓") {
		t.Fatal()
	}
	if !strings.Contains(SellBlockedReason(11, 10), "超过可用持仓") {
		t.Fatal()
	}
	if SellBlockedReason(5, 10) != "" {
		t.Fatal()
	}
}

func TestResolveSubmitPermission(t *testing.T) {
	ok, reason := ResolveSubmitPermission(false, true, true)
	if ok || reason != "仅扫描不下单" {
		t.Fatal(ok, reason)
	}
	ok, reason = ResolveSubmitPermission(true, false, true)
	if ok || !strings.Contains(reason, "凭据未配置") {
		t.Fatal(ok, reason)
	}
	ok, reason = ResolveSubmitPermission(true, true, false)
	if ok || !strings.Contains(reason, "未开启自动交易") {
		t.Fatal(ok, reason)
	}
	ok, reason = ResolveSubmitPermission(true, true, true)
	if !ok || reason != "" {
		t.Fatal(ok, reason)
	}
}

func TestFXCapsUseUSD(t *testing.T) {
	fx := FxRates{USDHKD: 7.8, USDCNY: 7.2}
	acct := Account{Configured: true, Balances: []Balance{
		{Currency: "HKD", NetAssets: 78000, AvailableCash: 78000},
	}}
	nav := PickNetAssets(acct, fx)
	if nav != 10000 {
		t.Fatalf("nav=%v", nav)
	}
	if DailyBuyCap(nav, 0.2) != 2000 {
		t.Fatalf("cap=%v", DailyBuyCap(nav, 0.2))
	}
}

func TestMergeRuntimeConfigDropsUnsafeKeys(t *testing.T) {
	cfg := MergeRuntimeConfig(map[string]interface{}{
		"require_paper":             false,
		"auto_execute":              true,
		"max_daily_orders":          99,
		"max_daily_notional_amount": 1e9,
		"max_symbols":               50,
		"min_confidence":            80,
	})
	if _, ok := cfg["require_paper"]; ok {
		t.Fatal("require_paper must not leak into runtime config")
	}
	if cfg["auto_execute"] != false {
		t.Fatal("client cannot raise auto_execute")
	}
	if cfg["max_daily_orders"] != 10 {
		t.Fatal("client cannot raise daily orders")
	}
	if cfg["max_symbols"] != 20 {
		t.Fatalf("max_symbols clamped to 20, got %v", cfg["max_symbols"])
	}
	if cfg["min_confidence"] != 80 {
		t.Fatal(cfg["min_confidence"])
	}
}

func TestRoundLimitPrice(t *testing.T) {
	if got := RoundLimitPrice(12.344, "US"); got != 12.34 {
		t.Fatalf("got %v", got)
	}
	if got := RoundLimitPrice(0.12344, "US"); got < 0.1234-1e-9 || got > 0.1234+1e-9 {
		t.Fatalf("got %v", got)
	}
	if got := RoundLimitPrice(0.1234, "HK"); got < 0.123-1e-9 || got > 0.123+1e-9 {
		t.Fatalf("hk tick %v", got)
	}
}
