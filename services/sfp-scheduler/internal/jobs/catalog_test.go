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
	if _, err := Resolve("not_a_job", "", ""); err == nil {
		t.Fatal("expected error for unknown go key")
	}
}

func TestResolveSentimentCollectEmptyKwargsAnalyzes(t *testing.T) {
	spec, err := Resolve("sentiment_collect", "", "")
	if err != nil {
		t.Fatal(err)
	}
	if spec.Payload["analyze"] != true {
		t.Fatalf("job 100 empty job_kwargs must analyze, payload=%v", spec.Payload)
	}
	spec, err = Resolve("sentiment_collect", "", "{}")
	if err != nil {
		t.Fatal(err)
	}
	if spec.Payload["analyze"] != true {
		t.Fatalf("empty object kwargs must analyze, payload=%v", spec.Payload)
	}
	spec, err = Resolve("sentiment_collect", "", `{"analyze":false}`)
	if err != nil {
		t.Fatal(err)
	}
	if spec.Payload["analyze"] != false {
		t.Fatalf("explicit false must stay collect-only, payload=%v", spec.Payload)
	}
}

func TestResolveGoNativeAliasesMatchPythonPaths(t *testing.T) {
	cases := []struct {
		pythonTarget string
		goTarget     string
		jobArgs      string
		jobKwargs    string
	}{
		{"module_task.sentiment_task.collect_and_analyze_job", "sentiment_collect", "", `{"analyze":true}`},
		{"module_task.sentiment_task.collect_only_job", "sentiment_collect", "", `{"analyze":false}`},
		{"module_task.market_task.sync_market_job", "market_sync", "", ""},
		{"module_task.market_task.sync_klines_slow_job", "klines_slow", "", `{"years":8}`},
		{"module_task.market_task.sync_listings_job", "listings_sync", "", ""},
		{"module_task.market_task.refresh_finance_briefings_job", "finance_briefings", "", ""},
		{"module_task.market_task.refresh_symbol_content_job", "symbol_content", "", ""},
		{"module_task.market_task.analyze_watchlist_job", "watchlist_analyze", "", ""},
		{"module_task.market_task.analyze_market_review_job", "market_review", "US", ""},
		{"module_task.market_task.collect_market_heat_cn_job", "market_heat_collect", "", `{"market":"CN"}`},
		{"module_task.market_task.collect_market_heat_hk_job", "market_heat_collect", "", `{"market":"HK"}`},
		{"module_task.market_task.collect_market_heat_us_job", "market_heat_collect", "", `{"market":"US"}`},
		{"module_task.market_task.eod_kline_sync_cn_job", "eod_kline_sync", "", `{"market":"CN"}`},
		{"module_task.market_task.eod_kline_sync_hk_job", "eod_kline_sync", "", `{"market":"HK"}`},
		{"module_task.market_task.eod_kline_sync_us_job", "eod_kline_sync", "", `{"market":"US"}`},
		{"module_task.market_task.run_stock_pick_job", "stock_pick_run", "", ""},
		{"module_task.quant_task.run_strategy_job", "strategy_run", "", ""},
		{"module_task.quant_task.run_daily_factor_scan_job", "factor_scan", "", ""},
		{"module_task.quant_task.run_position_monitor_job", "position_monitor", "", ""},
		{"module_task.quant_task.run_indicator_refresh_job", "indicator_refresh", "", ""},
		{"module_task.quant_task.run_factor_qc_job", "factor_qc", "", ""},
		{"module_task.quant_task.run_daily_list_scan_job", "daily_list_scan", "", ""},
		{"module_task.quant_task.run_daily_list_open_job", "daily_list_open", "", ""},
		{"module_task.trade_task.run_auto_trade_scan_job", "auto_trade_scan", "", ""},
		{"module_task.trade_task.run_feishu_push_job", "feishu_push", "", ""},
	}
	for _, tc := range cases {
		py, err := Resolve(tc.pythonTarget, tc.jobArgs, tc.jobKwargs)
		if err != nil {
			t.Fatalf("python %s: %v", tc.pythonTarget, err)
		}
		goSpec, err := Resolve(tc.goTarget, tc.jobArgs, tc.jobKwargs)
		if err != nil {
			t.Fatalf("go %s: %v", tc.goTarget, err)
		}
		if py.JobType != goSpec.JobType || py.Queue != goSpec.Queue {
			t.Fatalf("%s vs %s: py=%#v go=%#v", tc.pythonTarget, tc.goTarget, py, goSpec)
		}
		if !payloadEqual(py.Payload, goSpec.Payload) {
			t.Fatalf("%s vs %s payload py=%v go=%v", tc.pythonTarget, tc.goTarget, py.Payload, goSpec.Payload)
		}
	}
}

func TestResolveEnabledProductionJobsGoKeys(t *testing.T) {
	goKeys := map[int]string{
		101: "market_sync",
		103: "finance_briefings",
		104: "symbol_content",
		107: "indicator_refresh",
		113: "market_heat_collect",
		114: "market_heat_collect",
		115: "market_heat_collect",
		117: "feishu_push",
		121: "eod_kline_sync",
		122: "eod_kline_sync",
		123: "eod_kline_sync",
	}
	kwargs := map[int]string{
		113: `{"market":"CN"}`,
		114: `{"market":"HK"}`,
		115: `{"market":"US"}`,
		121: `{"market":"CN"}`,
		122: `{"market":"HK"}`,
		123: `{"market":"US"}`,
	}
	for _, id := range EnabledProductionIDs {
		target := goKeys[id]
		if target == "" {
			t.Fatalf("job %d missing canonical Go key", id)
		}
		kw := kwargs[id]
		spec, err := Resolve(target, "", kw)
		if err != nil {
			t.Fatalf("job %d key %s: %v", id, target, err)
		}
		if spec.JobType == "" {
			t.Fatalf("job %d empty job type", id)
		}
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
