package ingest_test

import (
	"testing"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/ingest"
)

func TestNormalizeTopicsArrayAndCSV(t *testing.T) {
	got := ingest.NormalizeTopics([]interface{}{"USEquity", " Fed ", ""})
	want := []string{"USEquity", "Fed"}
	if len(got) != len(want) || got[0] != want[0] || got[1] != want[1] {
		t.Fatalf("array topics: got %v want %v", got, want)
	}
	got = ingest.NormalizeTopics("SPX,QQQ/VIX，Macro")
	if len(got) != 4 || got[0] != "SPX" || got[3] != "Macro" {
		t.Fatalf("csv topics: got %v", got)
	}
	if ingest.NormalizeTopics(nil) != nil {
		t.Fatal("nil topics should be nil")
	}
}

func TestMapXMonitorItemForcesSourceAndHashesURL(t *testing.T) {
	url := "https://x.com/user/status/123"
	mapped := ingest.MapXMonitorItem(map[string]interface{}{
		"posted_at": "2026-09-04T10:00:00+08:00",
		"author":    "fed",
		"author_id": "99",
		"text":      "Rate cut chatter\nmore",
		"url":       url,
		"topics":    []interface{}{"Fed", "USEquity"},
		"source":    "client_spoof",
	})
	if mapped == nil {
		t.Fatal("expected mapped item")
	}
	if mapped.Source != "x_monitor" {
		t.Fatalf("source=%s", mapped.Source)
	}
	if mapped.Title != "Rate cut chatter" {
		t.Fatalf("title=%s", mapped.Title)
	}
	if mapped.UniqHash != ingest.URLHash(url) {
		t.Fatalf("hash=%s want %s", mapped.UniqHash, ingest.URLHash(url))
	}
	if mapped.PubTime.Hour() != 10 {
		t.Fatalf("hour=%d", mapped.PubTime.Hour())
	}
}

func TestMapXMonitorItemSkipsEmpty(t *testing.T) {
	if ingest.MapXMonitorItem(map[string]interface{}{"text": "", "url": ""}) != nil {
		t.Fatal("empty should skip")
	}
}

func TestVerifyToken(t *testing.T) {
	const token = "test-x-monitor-ingest-token"
	if err := ingest.VerifyToken("", token); err == nil {
		t.Fatal("missing token should fail")
	}
	if err := ingest.VerifyToken("wrong", token); err == nil {
		t.Fatal("wrong token should fail")
	}
	if err := ingest.VerifyToken(token, ""); err == nil {
		t.Fatal("unconfigured should fail")
	}
	if err := ingest.VerifyToken(token, token); err != nil {
		t.Fatalf("valid token: %v", err)
	}
}

func TestURLHashIdempotent(t *testing.T) {
	url := "https://x.com/fed/status/555"
	h1 := ingest.URLHash(url)
	h2 := ingest.URLHash(url)
	if h1 != h2 {
		t.Fatalf("hash not stable: %s vs %s", h1, h2)
	}
	if h1 == ingest.URLHash(url+"x") {
		t.Fatal("different urls should differ")
	}
}
