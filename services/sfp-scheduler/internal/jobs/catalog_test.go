package jobs

import (
	"fmt"
	"testing"
)

func TestResolveEnabledProductionJobs(t *testing.T) {
	cases := []struct {
		id      int
		target  string
		jobType string
		queue   QueueName
		payload map[string]any
	}{
		{101, "module_task.market_task.sync_market_job", "market_sync", QueueMarket, map[string]any{"years": 10}},
		{103, "module_task.market_task.refresh_finance_briefings_job", "finance_briefings", QueueMarket, map[string]any{}},
		{104, "module_task.market_task.refresh_symbol_content_job", "symbol_content", QueueMarket, map[string]any{}},
		{107, "module_task.quant_task.run_indicator_refresh_job", "indicator_refresh", QueueQuant, map[string]any{}},
		{113, "module_task.market_task.collect_market_heat_cn_job", "market_heat_collect", QueueMarket, map[string]any{"market": "CN", "tradeDate": nil}},
		{114, "module_task.market_task.collect_market_heat_hk_job", "market_heat_collect", QueueMarket, map[string]any{"market": "HK", "tradeDate": nil}},
		{115, "module_task.market_task.collect_market_heat_us_job", "market_heat_collect", QueueMarket, map[string]any{"market": "US", "tradeDate": nil}},
		{117, "module_task.trade_task.run_feishu_push_job", "feishu_push", QueueLLM, map[string]any{}},
		{121, "module_task.market_task.eod_kline_sync_cn_job", "eod_kline_sync", QueueMarket, map[string]any{"market": "CN"}},
		{122, "module_task.market_task.eod_kline_sync_hk_job", "eod_kline_sync", QueueMarket, map[string]any{"market": "HK"}},
		{123, "module_task.market_task.eod_kline_sync_us_job", "eod_kline_sync", QueueMarket, map[string]any{"market": "US"}},
	}
	seen := map[int]bool{}
	for _, tc := range cases {
		seen[tc.id] = true
		spec, err := Resolve(tc.target, "", "")
		if err != nil {
			t.Fatalf("job %d: %v", tc.id, err)
		}
		if spec.JobType != tc.jobType {
			t.Fatalf("job %d type=%s want=%s", tc.id, spec.JobType, tc.jobType)
		}
		if spec.Queue != tc.queue {
			t.Fatalf("job %d queue=%s want=%s", tc.id, spec.Queue, tc.queue)
		}
		if !payloadEqual(spec.Payload, tc.payload) {
			t.Fatalf("job %d payload=%v want=%v", tc.id, spec.Payload, tc.payload)
		}
	}
	for _, id := range EnabledProductionIDs {
		if !seen[id] {
			t.Fatalf("enabled production id %d missing from checklist", id)
		}
	}
}

func TestResolveQuantArgs(t *testing.T) {
	spec, err := Resolve("module_task.quant_task.run_strategy_job", "aggressive", `{"userId": 7}`)
	if err != nil {
		t.Fatal(err)
	}
	if spec.JobType != "strategy_run" || spec.Queue != QueueQuant {
		t.Fatalf("unexpected spec %#v", spec)
	}
	if spec.Payload["profile"] != "aggressive" {
		t.Fatalf("profile=%v", spec.Payload["profile"])
	}
	if spec.Payload["userId"] != 7 {
		t.Fatalf("userId=%v", spec.Payload["userId"])
	}
}

func TestResolveUnknownTarget(t *testing.T) {
	if _, err := Resolve("module_task.scheduler_test.job", "", ""); err == nil {
		t.Fatal("expected error")
	}
}

func payloadEqual(got, want map[string]any) bool {
	if len(got) != len(want) {
		return false
	}
	for k, wv := range want {
		gv, ok := got[k]
		if !ok {
			return false
		}
		if fmt.Sprint(gv) != fmt.Sprint(wv) {
			return false
		}
	}
	return true
}
