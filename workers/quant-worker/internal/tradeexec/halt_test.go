package tradeexec

import "testing"

func TestParseHalt(t *testing.T) {
	empty := ParseHalt("")
	if empty.Halted {
		t.Fatal("empty should not halt")
	}
	empty = ParseHalt("   ")
	if empty.Halted {
		t.Fatal("whitespace should not halt")
	}
	for _, raw := range []string{"1", "true", "TRUE", "Yes", "yes"} {
		h := ParseHalt(raw)
		if !h.Halted {
			t.Fatalf("%q should halt", raw)
		}
	}
	invalid := ParseHalt("not-json")
	if !invalid.Halted || invalid.Reason != "halt state unavailable" {
		t.Fatalf("invalid json: %+v", invalid)
	}
	ok := ParseHalt(`{"halted":true,"reason":"人工"}`)
	if !ok.Halted || ok.Reason != "人工" {
		t.Fatalf("valid json: %+v", ok)
	}
	off := ParseHalt(`{"halted":false,"reason":""}`)
	if off.Halted {
		t.Fatalf("valid json not halted: %+v", off)
	}
}

func TestFloorOrderQuantity(t *testing.T) {
	if _, msg := FloorOrderQuantity(0.5, "US"); msg == "" {
		t.Fatal("qty < 1 must reject")
	}
	qty, msg := FloorOrderQuantity(1.9, "US")
	if msg != "" || qty != 1 {
		t.Fatalf("us floor qty=%d msg=%q", qty, msg)
	}
	if _, msg := FloorOrderQuantity(50, "HK"); msg == "" {
		t.Fatal("hk below lot must reject")
	}
	qty, msg = FloorOrderQuantity(250.7, "HK")
	if msg != "" || qty != 200 {
		t.Fatalf("hk snap qty=%d msg=%q", qty, msg)
	}
}
