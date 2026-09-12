package ingest

import (
	"bytes"
	"strings"
	"testing"
	"unicode/utf8"
)

func TestClipRunes(t *testing.T) {
	if got := clipRunes("", 80); got != "" {
		t.Fatalf("empty: %q", got)
	}
	if got := clipRunes("short", 80); got != "short" {
		t.Fatalf("already-short: %q", got)
	}
	if got := clipRunes("hello", 0); got != "" {
		t.Fatalf("max 0: %q", got)
	}

	cjk := strings.Repeat("市", 30)
	if len(cjk) <= 80 {
		t.Fatalf("fixture bytes=%d", len(cjk))
	}
	if got := clipRunes(cjk, 80); got != cjk || !utf8.ValidString(got) {
		t.Fatalf("cjk under rune cap: %q valid=%v", got, utf8.ValidString(got))
	}

	// 78 ASCII + em dash: byte 80 is the middle of U+2014 (E2 80 94).
	mid := strings.Repeat("x", 78) + "\u2014" + "tail"
	old := mid[:80]
	if utf8.ValidString(old) || !bytes.Equal([]byte(old[78:]), []byte{0xE2, 0x80}) {
		t.Fatalf("bug fixture changed: %x", old)
	}
	got := clipRunes(mid, 80)
	if !utf8.ValidString(got) {
		t.Fatalf("em-dash clip invalid: %x", got)
	}
	if bytes.HasSuffix([]byte(got), []byte{0xE2, 0x80}) {
		t.Fatalf("incomplete \\xE2\\x80 prefix: %x", got)
	}
	if !strings.Contains(got, "\u2014") {
		t.Fatalf("lost em dash: %q", got)
	}
	if utf8.RuneCountInString(got) > 80 {
		t.Fatalf("runes=%d", utf8.RuneCountInString(got))
	}

	quote := strings.Repeat("y", 78) + "\u201c" + strings.Repeat("z", 10)
	got = clipRunes(quote, 80)
	if !utf8.ValidString(got) || !strings.Contains(got, "\u201c") {
		t.Fatalf("smart quote: %q hex=%x", got, []byte(got))
	}

	longCJK := strings.Repeat("涨", 120)
	got = clipRunes(longCJK, 80)
	if got != strings.Repeat("涨", 80) || !utf8.ValidString(got) {
		t.Fatalf("cjk clip: runes=%d valid=%v", utf8.RuneCountInString(got), utf8.ValidString(got))
	}

	url := "https://example.com/" + strings.Repeat("路", 90)
	got = clipRunes(url, 80)
	if !utf8.ValidString(got) || utf8.RuneCountInString(got) != 80 {
		t.Fatalf("url: %q runes=%d valid=%v", got, utf8.RuneCountInString(got), utf8.ValidString(got))
	}

	invalid := "ok" + string([]byte{0xE2, 0x80}) + "end"
	got = clipRunes(invalid, 80)
	if !utf8.ValidString(got) {
		t.Fatalf("invalid input should be repaired: %x", got)
	}
}
