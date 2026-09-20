package store

import (
	"os"
	"strings"
	"testing"
)

func TestMarketBenchmarksUseSuffixedCNHK(t *testing.T) {
	for _, pair := range marketBenchmarks["CN"] {
		sym := pair[0]
		if !strings.HasSuffix(sym, ".SH") && !strings.HasSuffix(sym, ".SZ") && !strings.HasSuffix(sym, ".SS") {
			t.Fatalf("CN briefing benchmark must be suffixed, got %q", sym)
		}
		if sym == "000001" {
			t.Fatal("CN briefing must not use bare 000001")
		}
	}
	for _, pair := range marketBenchmarks["HK"] {
		sym := pair[0]
		if !strings.Contains(sym, ".") && sym != "HSI" && sym != "HSTECH" && sym != "HSCEI" {
			t.Fatalf("HK briefing benchmark should be an index code, got %q", sym)
		}
	}
	for _, pair := range marketBenchmarks["US"] {
		if !strings.HasPrefix(pair[0], "^") {
			t.Fatalf("US briefing index should stay caret form, got %q", pair[0])
		}
	}
}

func TestBriefingsDoNotFluxQuery(t *testing.T) {
	body, err := os.ReadFile("briefings.go")
	if err != nil {
		t.Fatal(err)
	}
	text := string(body)
	for _, banned := range []string{"QueryKlines", "from(bucket", "/api/v2/query"} {
		if strings.Contains(text, banned) {
			t.Fatalf("finance_briefings still Flux-reads via %q", banned)
		}
	}
	if !strings.Contains(text, "latestDailyBars") {
		t.Fatal("finance_briefings should read MySQL daily bars")
	}
}

func TestInsertBriefingsSQLMatchesProductionSchema(t *testing.T) {
	sql := strings.ToLower(insertBriefingsSQL)
	if strings.Contains(sql, "create_time") || strings.Contains(sql, "update_time") {
		t.Fatalf("finance_briefing has no audit columns: %s", insertBriefingsSQL)
	}
	for _, col := range []string{
		"market", "briefing_type", "headline", "summary", "source_name",
		"source_link", "payload_json", "generated_at", "expires_at",
	} {
		if !strings.Contains(sql, col) {
			t.Fatalf("missing column %s in insert SQL", col)
		}
	}
	placeholderCount := strings.Count(insertBriefingsSQL, "?")
	if placeholderCount != 9 {
		t.Fatalf("expected 9 placeholders, got %d", placeholderCount)
	}
}
