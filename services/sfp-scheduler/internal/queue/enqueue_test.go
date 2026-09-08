package queue

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/lusd2904/smart-finance-platform/services/sfp-scheduler/internal/jobs"
)

func TestEncodePayloadShapeMatchesPython(t *testing.T) {
	loc, err := time.LoadLocation("Asia/Shanghai")
	if err != nil {
		t.Fatal(err)
	}
	cases := []struct {
		id      int
		target  string
		jobType string
		queue   string
	}{
		{101, "module_task.market_task.sync_market_job", "market_sync", "market"},
		{103, "module_task.market_task.refresh_finance_briefings_job", "finance_briefings", "market"},
		{104, "module_task.market_task.refresh_symbol_content_job", "symbol_content", "market"},
		{107, "module_task.quant_task.run_indicator_refresh_job", "indicator_refresh", "quant"},
		{113, "module_task.market_task.collect_market_heat_cn_job", "market_heat_collect", "market"},
		{114, "module_task.market_task.collect_market_heat_hk_job", "market_heat_collect", "market"},
		{115, "module_task.market_task.collect_market_heat_us_job", "market_heat_collect", "market"},
		{117, "module_task.trade_task.run_feishu_push_job", "feishu_push", "llm"},
		{121, "module_task.market_task.eod_kline_sync_cn_job", "eod_kline_sync", "market"},
		{122, "module_task.market_task.eod_kline_sync_hk_job", "eod_kline_sync", "market"},
		{123, "module_task.market_task.eod_kline_sync_us_job", "eod_kline_sync", "market"},
	}
	for _, tc := range cases {
		spec, err := jobs.Resolve(tc.target, "", "")
		if err != nil {
			t.Fatalf("job %d resolve: %v", tc.id, err)
		}
		raw, job, err := Encode(spec.JobType, spec.Payload, loc, "abc123def456")
		if err != nil {
			t.Fatalf("job %d encode: %v", tc.id, err)
		}
		var decoded map[string]any
		if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
			t.Fatalf("job %d json: %v", tc.id, err)
		}
		for _, key := range []string{"type", "payload", "jobId", "queue", "enqueuedAt"} {
			if _, ok := decoded[key]; !ok {
				t.Fatalf("job %d missing key %s in %s", tc.id, key, raw)
			}
		}
		if decoded["type"] != tc.jobType {
			t.Fatalf("job %d type=%v", tc.id, decoded["type"])
		}
		if decoded["queue"] != tc.queue {
			t.Fatalf("job %d queue=%v", tc.id, decoded["queue"])
		}
		if decoded["jobId"] != "abc123def456" {
			t.Fatalf("job %d jobId=%v", tc.id, decoded["jobId"])
		}
		if _, err := time.ParseInLocation(TimeLayout, job.EnqueuedAt, loc); err != nil {
			t.Fatalf("job %d enqueuedAt %q: %v", tc.id, job.EnqueuedAt, err)
		}
		roundtrip, err := Decode(raw)
		if err != nil {
			t.Fatalf("job %d decode: %v", tc.id, err)
		}
		if roundtrip.Type != tc.jobType || roundtrip.Queue != tc.queue {
			t.Fatalf("job %d roundtrip %#v", tc.id, roundtrip)
		}
	}
}

func TestEncodeHeatPayloadKeepsNullTradeDate(t *testing.T) {
	spec, err := jobs.Resolve("module_task.market_task.collect_market_heat_us_job", "", "")
	if err != nil {
		t.Fatal(err)
	}
	raw, _, err := Encode(spec.JobType, spec.Payload, time.UTC, "heat1")
	if err != nil {
		t.Fatal(err)
	}
	var decoded map[string]any
	if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
		t.Fatal(err)
	}
	payload, _ := decoded["payload"].(map[string]any)
	if payload["market"] != "US" {
		t.Fatalf("market=%v", payload["market"])
	}
	if payload["tradeDate"] != nil {
		t.Fatalf("tradeDate=%v want null", payload["tradeDate"])
	}
}

func TestEncodeRejectsUnknownType(t *testing.T) {
	if _, _, err := Encode("not_a_job", map[string]any{}, time.UTC, ""); err == nil {
		t.Fatal("expected error")
	}
}

func TestQueueKeys(t *testing.T) {
	if jobs.QueueKey(jobs.QueueMarket) != "sfp:job:queue:market" {
		t.Fatal(jobs.QueueKey(jobs.QueueMarket))
	}
	if jobs.QueueKey(jobs.QueueQuant) != "sfp:job:queue:quant" {
		t.Fatal(jobs.QueueKey(jobs.QueueQuant))
	}
	if jobs.QueueKey(jobs.QueueLLM) != "sfp:job:queue:llm" {
		t.Fatal(jobs.QueueKey(jobs.QueueLLM))
	}
}
