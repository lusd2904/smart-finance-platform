package jobs

import "fmt"

// DeferredJobReason documents why a job is not yet native in Go.
var DeferredJobReason = map[string]string{
	"watchlist_analyze": "needs FactorService + StockPickAnalyzer + Influx klines (market-worker scope)",
	"stock_pick_run":    "needs full stock pick scoring engine + heat/mood assembly (data-api scope)",
	"market_review":     "needs Influx benchmark context + MarketReviewAiAnalyzer",
	"ai_analyze":        "needs StockPickService.analyze_symbol (shared with watchlist)",
	"ai_batch":          "depends on native ai_analyze",
}

func RunDeferred(jobType string) (map[string]interface{}, error) {
	reason := DeferredJobReason[jobType]
	if reason == "" {
		reason = "not yet implemented in native Go worker"
	}
	return map[string]interface{}{
		"skipped": true,
		"reason":  jobType + "_deferred",
		"message": fmt.Sprintf("Job %s is intentionally stubbed in sfp-notify-worker: %s", jobType, reason),
	}, nil
}
