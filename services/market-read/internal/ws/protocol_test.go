package ws

import (
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/market-read/internal/quotes"
)

func TestNormalizeInterval(t *testing.T) {
	if NormalizeInterval("") != 15 {
		t.Fatal("default")
	}
	if NormalizeInterval("abc") != 15 {
		t.Fatal("invalid")
	}
	if NormalizeInterval("1") != 3 {
		t.Fatal("min")
	}
	if NormalizeInterval("999") != 60 {
		t.Fatal("max")
	}
	if NormalizeInterval("10") != 10 {
		t.Fatal("pass-through")
	}
}

func TestParseClientFrame(t *testing.T) {
	if parseClientFrame("ping").Kind != kindPing {
		t.Fatal("ping")
	}
	frame := parseClientFrame(`{"type":"subscribe","symbols":["AAPL:US"]}`)
	if frame.Kind != kindSubscribe {
		t.Fatalf("kind=%s", frame.Kind)
	}
	if len(frame.Symbols) != 1 || frame.Symbols[0] != (quotes.Pair{Symbol: "AAPL", Market: "US"}) {
		t.Fatalf("symbols=%#v", frame.Symbols)
	}
	unsubAll := parseClientFrame(`{"type":"unsubscribe"}`)
	if unsubAll.Kind != kindUnsubscribe || unsubAll.Symbols == nil {
		t.Fatalf("unsubscribe all %#v", unsubAll)
	}
	if tokenFromAuthFrame(`{"type":"auth","token":"abc"}`) != "abc" {
		t.Fatal("auth token")
	}
	if tokenFromAuthFrame("ping") != "" {
		t.Fatal("ping is not auth")
	}
}
