package jobs

import (
	"context"
	"fmt"

	"github.com/lusd2904/smart-finance-platform/services/sfp-intel/internal/store"
)

type Runner struct {
	Store *store.Store
}

var known = map[string]bool{
	"sentiment_collect": true, "sentiment_analyze": true, "watchlist_analyze": true,
	"daily_review": true, "req_send": true, "req_summarize": true, "stock_pick_run": true,
	"market_review": true, "ai_analyze": true, "ai_batch": true, "user_notice": true,
}

func (r *Runner) Run(ctx context.Context, jobType string, payload map[string]interface{}) (map[string]interface{}, error) {
	if r == nil || r.Store == nil {
		return nil, fmt.Errorf("job runner not configured")
	}
	if !known[jobType] {
		return nil, fmt.Errorf("unknown llm job type: %s", jobType)
	}
	switch jobType {
	case "sentiment_analyze":
		return r.Store.RunSentimentAnalysis(ctx)
	case "sentiment_collect":
		return map[string]interface{}{
			"inserted": 0, "message": "采集由 X-monitor ingest / 外部源写入；Go 定时任务仅触发分析",
			"analyze": payload != nil && fmt.Sprint(payload["analyze"]) == "true",
		}, nil
	case "user_notice":
		return map[string]interface{}{"ok": true, "message": "user_notice ack (Go)"}, nil
	default:
		return map[string]interface{}{
			"skipped": true, "type": jobType,
			"message": "LLM job pending full Go port; enable legacy-intel profile for Python fallback",
		}, nil
	}
}
