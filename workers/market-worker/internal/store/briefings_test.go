package store

import (
	"strings"
	"testing"
)

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
