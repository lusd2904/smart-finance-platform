package ingest_test

import (
	"bytes"
	"strings"
	"testing"
	"unicode/utf8"

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

func assertSafeUTF8(t *testing.T, label, s string) {
	t.Helper()
	if !utf8.ValidString(s) {
		t.Fatalf("%s is not utf8.ValidString: %q hex=%x", label, s, []byte(s))
	}
	b := []byte(s)
	if bytes.HasSuffix(b, []byte{0xE2}) || bytes.HasSuffix(b, []byte{0xE2, 0x80}) {
		t.Fatalf("%s ends with incomplete U+201x prefix (MySQL would reject \\xE2\\x80): hex=%x", label, b)
	}
}

func TestMapXMonitorItemClipsUTF8ByRunes(t *testing.T) {
	t.Run("empty", func(t *testing.T) {
		if ingest.MapXMonitorItem(map[string]interface{}{"text": "", "url": ""}) != nil {
			t.Fatal("empty text+url should skip")
		}
		if ingest.MapXMonitorItem(map[string]interface{}{"text": "   ", "url": nil}) != nil {
			t.Fatal("whitespace-only should skip")
		}
	})

	t.Run("already-short", func(t *testing.T) {
		mapped := ingest.MapXMonitorItem(map[string]interface{}{"text": "Rate cut", "url": "https://x.com/a"})
		if mapped == nil || mapped.Title != "Rate cut" {
			t.Fatalf("title=%v", mapped)
		}
		assertSafeUTF8(t, "title", mapped.Title)
	})

	t.Run("80-plus-bytes-fewer-runes", func(t *testing.T) {
		// 30 CJK runes = 90 bytes, still under the 80-rune title clip.
		text := strings.Repeat("市", 30)
		if len(text) <= 80 || utf8.RuneCountInString(text) >= 80 {
			t.Fatalf("fixture: bytes=%d runes=%d", len(text), utf8.RuneCountInString(text))
		}
		mapped := ingest.MapXMonitorItem(map[string]interface{}{"text": text, "url": "https://x.com/a"})
		if mapped == nil {
			t.Fatal("expected mapped item")
		}
		if mapped.Title != text {
			t.Fatalf("title=%q want full %d-rune string", mapped.Title, utf8.RuneCountInString(text))
		}
		assertSafeUTF8(t, "title", mapped.Title)
	})

	t.Run("byte-80-inside-em-dash", func(t *testing.T) {
		// 78 ASCII + U+2014 (E2 80 94) puts byte 80 inside the 3-byte rune.
		// Old title[:80] yielded "...\xE2\x80" which MySQL utf8mb4 rejects.
		prefix := strings.Repeat("a", 78)
		text := prefix + "\u2014" + " more after dash and extra runes to exceed eighty"
		if got, want := text[78:81], "\u2014"; got != want {
			t.Fatalf("em dash bytes=%x want %x", got, want)
		}
		if text[79] != 0x80 {
			t.Fatalf("byte 80 (1-based) should be 0x80, got 0x%x", text[79])
		}
		oldCut := text[:80]
		if utf8.ValidString(oldCut) || !bytes.Equal([]byte(oldCut[78:]), []byte{0xE2, 0x80}) {
			t.Fatalf("fixture no longer reproduces the live bug: oldCut=%x valid=%v", oldCut, utf8.ValidString(oldCut))
		}
		mapped := ingest.MapXMonitorItem(map[string]interface{}{"text": text, "url": "https://x.com/a"})
		if mapped == nil {
			t.Fatal("expected mapped item")
		}
		assertSafeUTF8(t, "title", mapped.Title)
		if !strings.HasPrefix(mapped.Title, prefix+"\u2014") {
			t.Fatalf("title should keep the full em dash: %q hex=%x", mapped.Title, []byte(mapped.Title))
		}
		if utf8.RuneCountInString(mapped.Title) > 80 {
			t.Fatalf("title runes=%d", utf8.RuneCountInString(mapped.Title))
		}
	})

	t.Run("byte-80-inside-smart-quote", func(t *testing.T) {
		prefix := strings.Repeat("b", 78)
		text := prefix + "\u201c" + "quoted remainder that is long enough"
		if text[78:81] != "\u201c" {
			t.Fatalf("smart quote bytes=%x", text[78:81])
		}
		mapped := ingest.MapXMonitorItem(map[string]interface{}{"text": text})
		if mapped == nil {
			t.Fatal("expected mapped item")
		}
		assertSafeUTF8(t, "title", mapped.Title)
		if !strings.Contains(mapped.Title, "\u201c") {
			t.Fatalf("title dropped U+201C: %q hex=%x", mapped.Title, []byte(mapped.Title))
		}
	})

	t.Run("cjk-over-80-runes", func(t *testing.T) {
		text := strings.Repeat("涨", 100)
		mapped := ingest.MapXMonitorItem(map[string]interface{}{"text": text})
		if mapped == nil {
			t.Fatal("expected mapped item")
		}
		if got := utf8.RuneCountInString(mapped.Title); got != 80 {
			t.Fatalf("title runes=%d want 80", got)
		}
		if mapped.Title != strings.Repeat("涨", 80) {
			t.Fatalf("title=%q", mapped.Title)
		}
		assertSafeUTF8(t, "title", mapped.Title)
		assertSafeUTF8(t, "content", mapped.Content)
	})

	t.Run("url-utf8-title-fallback", func(t *testing.T) {
		url := "https://x.com/search?q=" + strings.Repeat("市", 40) + "\u2014trail"
		mapped := ingest.MapXMonitorItem(map[string]interface{}{"text": "", "url": url})
		if mapped == nil {
			t.Fatal("expected mapped item")
		}
		if mapped.URL == nil || *mapped.URL != url {
			t.Fatalf("stored url should stay full, got %v", mapped.URL)
		}
		assertSafeUTF8(t, "title", mapped.Title)
		assertSafeUTF8(t, "url", *mapped.URL)
		if utf8.RuneCountInString(mapped.Title) > 80 {
			t.Fatalf("title runes=%d", utf8.RuneCountInString(mapped.Title))
		}
		if !strings.HasPrefix(url, mapped.Title) && !strings.HasPrefix(mapped.Title, "https://x.com/search?q=") {
			t.Fatalf("title should be a rune-safe prefix of url: %q", mapped.Title)
		}
	})
}
