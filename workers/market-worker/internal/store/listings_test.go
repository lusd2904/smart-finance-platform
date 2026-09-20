package store

import (
	"context"
	"os"
	"strings"
	"testing"
)

func TestListedFromMySQLSQL(t *testing.T) {
	sql := strings.ToLower(listedFromMySQLSQL)
	for _, frag := range []string{
		"select distinct symbol, market",
		"from market_price_history_daily",
	} {
		if !strings.Contains(sql, frag) {
			t.Fatalf("missing %q in %s", frag, listedFromMySQLSQL)
		}
	}
	if strings.Contains(sql, "from(") || strings.Contains(sql, "schema.tagvalues") {
		t.Fatal("listings_sync must not Flux")
	}
}

func TestListingsSourceFileHasNoFluxRead(t *testing.T) {
	body, err := os.ReadFile("listings.go")
	if err != nil {
		t.Fatal(err)
	}
	text := string(body)
	for _, banned := range []string{"ListSymbols", "from(bucket", "/api/v2/query", "schema.tagValues"} {
		if strings.Contains(text, banned) {
			t.Fatalf("listings.go still Flux-reads via %q", banned)
		}
	}
	if !strings.Contains(text, `"mysql"`) {
		t.Fatal("listings_sync result source should be mysql")
	}
}

func TestSyncListedFromMySQLEmptyWithoutDB(t *testing.T) {
	s := &Service{}
	out, err := s.SyncListedFromMySQL(context.Background())
	if err != nil {
		t.Fatalf("empty MySQL listing must not error: %v", err)
	}
	if out["source"] != "mysql" {
		t.Fatalf("source=%v", out["source"])
	}
	if out["upserted"] != 0 {
		t.Fatalf("upserted=%v", out["upserted"])
	}
}
