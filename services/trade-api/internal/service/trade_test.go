package service

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/trade-exec"
	"github.com/redis/go-redis/v9"
)

func TestReadHaltFailClosed(t *testing.T) {
	s := &Trade{}
	h := s.ReadHalt(context.Background())
	if !h.Halted || h.Reason != "halt state unavailable" {
		t.Fatalf("nil redis: %+v", h)
	}

	s.Redis = redis.NewClient(&redis.Options{Addr: "127.0.0.1:1", DialTimeout: 50 * time.Millisecond})
	h = s.ReadHalt(context.Background())
	if !h.Halted || h.Reason != "halt state unavailable" {
		t.Fatalf("get error: %+v", h)
	}
}

func TestWriteHaltSurfacesSetError(t *testing.T) {
	s := &Trade{}
	_, err := s.WriteHalt(context.Background(), true, "x", 2)
	if err == nil || !strings.Contains(err.Error(), "unavailable") {
		t.Fatalf("nil redis err=%v", err)
	}
	s.Redis = redis.NewClient(&redis.Options{Addr: "127.0.0.1:1", DialTimeout: 50 * time.Millisecond})
	_, err = s.WriteHalt(context.Background(), true, "x", 2)
	if err == nil {
		t.Fatal("SET failure must surface")
	}
}

func TestParseHaltViaRead(t *testing.T) {
	h := tradeexec.ParseHalt("")
	if h.Halted {
		t.Fatal("empty")
	}
}
