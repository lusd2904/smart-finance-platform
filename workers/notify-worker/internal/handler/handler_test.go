package handler

import "testing"

func TestAllLLMJobsAreNative(t *testing.T) {
	for _, jobType := range []string{
		"sentiment_collect", "sentiment_analyze", "watchlist_analyze",
		"daily_review", "req_send", "req_summarize", "feishu_push",
		"stock_pick_run", "market_review", "ai_analyze", "ai_batch", "user_notice",
	} {
		if !nativeJobs[jobType] {
			t.Fatalf("%s should be handled natively", jobType)
		}
	}
}

func TestDeferredJobTypesDocumented(t *testing.T) {
	if len(DeferredJobTypes()) != 0 {
		t.Fatalf("all llm jobs should be native, deferred=%v", DeferredJobTypes())
	}
}
