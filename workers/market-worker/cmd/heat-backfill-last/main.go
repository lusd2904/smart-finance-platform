package main

import (
	"context"
	"encoding/json"
	"flag"
	"log"
	"os"
	"strings"

	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/config"
	"github.com/lusd2904/smart-finance-platform/workers/market-worker/internal/store"
)

func main() {
	var (
		startDate = flag.String("from", "", "Start trade date YYYY-MM-DD (required)")
		endDate   = flag.String("to", "", "End trade date YYYY-MM-DD inclusive (required)")
		market    = flag.String("market", "ALL", "Market CN/HK/US or ALL")
		dryRun    = flag.Bool("dry-run", false, "Report counts without writing")
	)
	flag.Parse()
	if strings.TrimSpace(*startDate) == "" || strings.TrimSpace(*endDate) == "" {
		log.Fatal("both --from and --to are required")
	}

	cfg := config.Load()
	svc, err := store.NewMySQLOnly(cfg)
	if err != nil {
		log.Fatalf("mysql: %v", err)
	}
	defer svc.Close()

	markets := []string{strings.ToUpper(strings.TrimSpace(*market))}
	if markets[0] == "ALL" {
		markets = []string{"CN", "HK", "US"}
	}

	agg := map[string]interface{}{
		"startDate": strings.TrimSpace(*startDate)[:10],
		"endDate":   strings.TrimSpace(*endDate)[:10],
		"dryRun":    *dryRun,
		"byMarket":  map[string]interface{}{},
	}
	totalScanned := 0
	totalPatched := 0
	totalMissing := 0
	byMarket := agg["byMarket"].(map[string]interface{})

	for _, mkt := range markets {
		result, err := svc.BackfillTop50Last(context.Background(), mkt, *startDate, *endDate, *dryRun)
		if err != nil {
			log.Fatalf("%s: %v", mkt, err)
		}
		byMarket[mkt] = result
		totalScanned += intFrom(result["scanned"])
		totalPatched += intFrom(result["patched"])
		totalMissing += intFrom(result["stillMissing"])
	}
	agg["scanned"] = totalScanned
	agg["patched"] = totalPatched
	agg["stillMissing"] = totalMissing

	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(agg); err != nil {
		log.Fatal(err)
	}
}

func intFrom(v interface{}) int {
	switch n := v.(type) {
	case int:
		return n
	case int64:
		return int(n)
	case float64:
		return int(n)
	default:
		return 0
	}
}
